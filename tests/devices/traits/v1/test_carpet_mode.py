"""Public carpet boost behavior using simulated RPC responses."""

import asyncio
from dataclasses import replace
from unittest.mock import AsyncMock, call

import pytest

from roborock.data import HomeData, HomeDataDevice
from roborock.data.v1.v1_containers import CarpetModeSettings
from roborock.devices.device import RoborockDevice
from roborock.devices.traits.v1.carpet_mode import CarpetModeTrait
from roborock.devices.traits.v1.common import V1ResponseData
from roborock.exceptions import RoborockParsingException, RoborockTimeout, RoborockUnsupportedFeature
from roborock.roborock_typing import RoborockCommand

# Values from the read-only a294 capture; these are not evidence of device writes.
CAPTURED_SETTINGS = {
    "enable": 1,
    "current_integral": 1000,
    "current_high": 500,
    "current_low": 1000,
    "stall_time": 10,
}


@pytest.fixture
def carpet_supported() -> bool:
    return True


@pytest.fixture(name="device_info")
def device_info_fixture(trait_home_data: HomeData, carpet_supported: bool) -> HomeDataDevice:
    """Set the documented carpet feature bit for shared discovery fixtures."""
    device_info = trait_home_data.get_all_devices()[0]
    assert device_info.new_feature_set is not None
    flags = int(device_info.new_feature_set, 16)
    flags = flags | 512 if carpet_supported else flags & ~512
    return replace(device_info, new_feature_set=f"{flags:016x}")


@pytest.fixture
def carpet_mode(device: RoborockDevice, discover_features_fixture: None) -> CarpetModeTrait:
    assert device.v1_properties is not None
    assert device.v1_properties.carpet_mode is not None
    return device.v1_properties.carpet_mode


@pytest.mark.parametrize("carpet_supported", [True, False])
async def test_discovery(device: RoborockDevice, carpet_supported: bool, discover_features_fixture: None) -> None:
    """Discovery follows the carpet feature bit."""
    assert device.v1_properties is not None
    assert (device.v1_properties.carpet_mode is not None) is carpet_supported


def test_unrefreshed(carpet_mode: CarpetModeTrait) -> None:
    assert carpet_mode.settings is None
    assert not carpet_mode.is_on
    assert carpet_mode.as_dict() == {}


@pytest.mark.parametrize("wrapped", [True, False])
async def test_refresh(carpet_mode: CarpetModeTrait, mock_rpc_channel: AsyncMock, wrapped: bool) -> None:
    """Both legacy response shapes preserve the captured tuning exactly."""
    mock_rpc_channel.send_command.return_value = [CAPTURED_SETTINGS] if wrapped else CAPTURED_SETTINGS
    await carpet_mode.refresh()
    assert carpet_mode.settings == CarpetModeSettings(**CAPTURED_SETTINGS)
    assert carpet_mode.is_on
    mock_rpc_channel.send_command.assert_awaited_once_with(RoborockCommand.GET_CARPET_MODE)
    assert carpet_mode.as_dict() == {
        "settings": {"enable": 1, "currentIntegral": 1000, "currentHigh": 500, "currentLow": 1000, "stallTime": 10}
    }


@pytest.mark.parametrize("enabled", [True, False])
async def test_toggle(carpet_mode: CarpetModeTrait, mock_rpc_channel: AsyncMock, enabled: bool) -> None:
    """Each toggle fresh-reads tuning and uses a singleton snake-case SET."""
    mock_rpc_channel.send_command.return_value = {**CAPTURED_SETTINGS, "current_integral": 450}
    await carpet_mode.refresh()
    mock_rpc_channel.send_command.reset_mock()
    before = {**CAPTURED_SETTINGS, "enable": int(not enabled)}
    after = {**CAPTURED_SETTINGS, "enable": int(enabled)}
    mock_rpc_channel.send_command.side_effect = [[before], ["ok"], [after]]

    await (carpet_mode.enable() if enabled else carpet_mode.disable())

    assert mock_rpc_channel.send_command.await_args_list == [
        call(RoborockCommand.GET_CARPET_MODE),
        call(RoborockCommand.SET_CARPET_MODE, params=[after]),
        call(RoborockCommand.GET_CARPET_MODE),
    ]
    assert carpet_mode.settings == CarpetModeSettings(**after)
    assert carpet_mode.is_on is enabled


MALFORMED_RESPONSES = [
    None,
    1,
    "invalid",
    [],
    [CAPTURED_SETTINGS, CAPTURED_SETTINGS],
    [1],
    [[CAPTURED_SETTINGS]],
    *[{key: value for key, value in CAPTURED_SETTINGS.items() if key != missing} for missing in CAPTURED_SETTINGS],
    *[{**CAPTURED_SETTINGS, field: value} for field in CAPTURED_SETTINGS for value in (True, "1", 1.5, None)],
]


@pytest.mark.parametrize("response", MALFORMED_RESPONSES)
async def test_malformed_read_blocks_write(
    carpet_mode: CarpetModeTrait, mock_rpc_channel: AsyncMock, response: V1ResponseData | None
) -> None:
    """An incomplete or malformed fresh read leaves old state and never SETs."""
    mock_rpc_channel.send_command.return_value = CAPTURED_SETTINGS
    await carpet_mode.refresh()
    previous = carpet_mode.settings
    mock_rpc_channel.send_command.reset_mock()
    mock_rpc_channel.send_command.return_value = response
    with pytest.raises(RoborockParsingException, match="GET_CARPET_MODE.*CarpetModeTrait") as error:
        await carpet_mode.disable()
    assert isinstance(error.value.__cause__, (TypeError, ValueError))
    assert carpet_mode.settings == previous
    assert carpet_mode.is_on
    mock_rpc_channel.send_command.assert_awaited_once_with(RoborockCommand.GET_CARPET_MODE)


@pytest.mark.parametrize(
    "response",
    [{**CAPTURED_SETTINGS, "new_tuning": 42}, {**CAPTURED_SETTINGS, "enable": 2}],
)
@pytest.mark.parametrize("enabled", [True, False])
async def test_unknown_schema(
    carpet_mode: CarpetModeTrait, mock_rpc_channel: AsyncMock, response: dict[str, int], enabled: bool
) -> None:
    """Known getter values remain visible while unknown schemas block writing."""
    mock_rpc_channel.send_command.return_value = response
    await carpet_mode.refresh()
    expected = CarpetModeSettings(**{key: response[key] for key in CAPTURED_SETTINGS})
    assert carpet_mode.settings == expected
    assert carpet_mode.is_on is (response["enable"] == 1)
    mock_rpc_channel.send_command.reset_mock()
    with pytest.raises(RoborockUnsupportedFeature, match="five-field legacy schema"):
        await (carpet_mode.enable() if enabled else carpet_mode.disable())
    assert carpet_mode.settings == expected
    mock_rpc_channel.send_command.assert_awaited_once_with(RoborockCommand.GET_CARPET_MODE)


@pytest.mark.parametrize("failure_stage", [0, 1, 2])
async def test_rpc_failure(carpet_mode: CarpetModeTrait, mock_rpc_channel: AsyncMock, failure_stage: int) -> None:
    """Failures preserve the last complete read and stop the RPC sequence."""
    old = {**CAPTURED_SETTINGS, "current_integral": 450}
    fresh = {**CAPTURED_SETTINGS, "enable": 0}
    mock_rpc_channel.send_command.return_value = old
    await carpet_mode.refresh()
    mock_rpc_channel.send_command.reset_mock()
    error = RoborockTimeout("simulated failure")
    mock_rpc_channel.send_command.side_effect = [fresh, ["ok"]][:failure_stage] + [error]
    with pytest.raises(RoborockTimeout) as caught:
        await carpet_mode.enable()
    assert caught.value is error
    assert carpet_mode.settings == CarpetModeSettings(**(old if failure_stage == 0 else fresh))
    assert (
        mock_rpc_channel.send_command.await_args_list
        == [
            call(RoborockCommand.GET_CARPET_MODE),
            call(RoborockCommand.SET_CARPET_MODE, params=[{**fresh, "enable": 1}]),
            call(RoborockCommand.GET_CARPET_MODE),
        ][: failure_stage + 1]
    )


async def test_malformed_readback(carpet_mode: CarpetModeTrait, mock_rpc_channel: AsyncMock) -> None:
    """A failed readback retains the fresh initial read without optimism."""
    before = {**CAPTURED_SETTINGS, "enable": 0}
    mock_rpc_channel.send_command.side_effect = [before, ["ok"], []]
    with pytest.raises(RoborockParsingException):
        await carpet_mode.enable()
    assert carpet_mode.settings == CarpetModeSettings(**before)
    assert not carpet_mode.is_on
    assert mock_rpc_channel.send_command.await_count == 3


async def test_readback_is_authoritative(carpet_mode: CarpetModeTrait, mock_rpc_channel: AsyncMock) -> None:
    """Successful SET acknowledgment does not fabricate enabled state."""
    before = {**CAPTURED_SETTINGS, "enable": 0}
    reported = {**before, "current_integral": 900}
    mock_rpc_channel.send_command.side_effect = [before, ["ok"], reported]
    await carpet_mode.enable()
    assert carpet_mode.settings == CarpetModeSettings(**reported)
    assert not carpet_mode.is_on


async def test_concurrent_toggles(carpet_mode: CarpetModeTrait, mock_rpc_channel: AsyncMock) -> None:
    """Concurrent toggles serialize whole cycles, fresh-reading each tuning set."""
    first_get_started = asyncio.Event()
    release_first_get = asyncio.Event()
    disable_started = asyncio.Event()
    first = {**CAPTURED_SETTINGS, "enable": 0}
    first_after = {**first, "enable": 1}
    second = {**first_after, "current_integral": 800, "current_high": -20}
    second_after = {**second, "enable": 0}
    reply_sequence: list[V1ResponseData] = [first, ["ok"], first_after, second, ["ok"], second_after]
    replies = iter(reply_sequence)

    async def send(command: RoborockCommand, params: list[dict[str, int]] | None = None) -> V1ResponseData:
        if not first_get_started.is_set():
            first_get_started.set()
            await release_first_get.wait()
        return next(replies)

    async def disable() -> None:
        disable_started.set()
        await carpet_mode.disable()

    mock_rpc_channel.send_command.side_effect = send
    async with asyncio.TaskGroup() as tasks:
        tasks.create_task(carpet_mode.enable())
        await first_get_started.wait()
        tasks.create_task(disable())
        await disable_started.wait()
        assert mock_rpc_channel.send_command.await_args_list == [call(RoborockCommand.GET_CARPET_MODE)]
        release_first_get.set()

    assert mock_rpc_channel.send_command.await_args_list == [
        call(RoborockCommand.GET_CARPET_MODE),
        call(RoborockCommand.SET_CARPET_MODE, params=[first_after]),
        call(RoborockCommand.GET_CARPET_MODE),
        call(RoborockCommand.GET_CARPET_MODE),
        call(RoborockCommand.SET_CARPET_MODE, params=[second_after]),
        call(RoborockCommand.GET_CARPET_MODE),
    ]
    assert carpet_mode.settings == CarpetModeSettings(**second_after)
    assert not carpet_mode.is_on
