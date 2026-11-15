"""Tests for the CarpetModeTrait class."""

from unittest.mock import AsyncMock, call

import pytest

from roborock.data import CarpetModeSettings, HomeDataDevice
from roborock.devices.device import RoborockDevice
from roborock.devices.traits.v1.carpet_mode import CarpetModeTrait
from roborock.exceptions import RoborockException, RoborockParsingException
from roborock.roborock_typing import RoborockCommand
from tests import mock_data

# The suite's default device (S7 MaxV fixture) does not report is_carpet_supported; the Saros 10R does.
SAROS_10R = mock_data.DEVICE_PRODUCT_PAIRS["home_data_device_saros_10r.json"][0]

# Captured from a Qrevo 2 Pro (roborock.vacuum.a294) via get_carpet_mode
CARPET_MODE_RESPONSE = [
    {"enable": 1, "current_integral": 1000, "current_high": 500, "current_low": 1000, "stall_time": 10}
]


@pytest.fixture(name="carpet_mode")
def carpet_mode_trait(
    device: RoborockDevice,
    discover_features_fixture: None,
) -> CarpetModeTrait | None:
    """Return the trait created by feature discovery."""
    assert device.v1_properties
    return device.v1_properties.carpet_mode


async def test_unsupported_without_carpet_feature(carpet_mode: CarpetModeTrait | None) -> None:
    """The trait is not created when the device does not report carpet support."""
    assert carpet_mode is None


@pytest.mark.parametrize("device_info", [SAROS_10R])
async def test_refresh(
    carpet_mode: CarpetModeTrait | None,
    device_info: HomeDataDevice,
    mock_rpc_channel: AsyncMock,
) -> None:
    """Refreshing reads the boost setting and motor tuning values."""
    assert carpet_mode is not None
    mock_rpc_channel.send_command.return_value = CARPET_MODE_RESPONSE

    await carpet_mode.refresh()

    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.GET_CARPET_MODE)
    assert carpet_mode.settings == CarpetModeSettings(
        enable=1, current_integral=1000, current_high=500, current_low=1000, stall_time=10
    )
    assert carpet_mode.is_on


@pytest.mark.parametrize("device_info", [SAROS_10R])
@pytest.mark.parametrize(
    "response",
    [
        pytest.param([{"enable": 1, "current_integral": 1000}], id="missing-field"),
        pytest.param([{**CARPET_MODE_RESPONSE[0], "current_integral": None}], id="null-field"),
        pytest.param([], id="empty-list"),
    ],
)
async def test_refresh_malformed_response(
    carpet_mode: CarpetModeTrait | None,
    device_info: HomeDataDevice,
    mock_rpc_channel: AsyncMock,
    response: list,
) -> None:
    """A malformed response is rejected and the previously read values are kept."""
    assert carpet_mode is not None
    mock_rpc_channel.send_command.return_value = CARPET_MODE_RESPONSE
    await carpet_mode.refresh()
    previous = carpet_mode.settings

    mock_rpc_channel.send_command.return_value = response
    with pytest.raises(RoborockParsingException):
        await carpet_mode.refresh()

    assert carpet_mode.settings == previous


@pytest.mark.parametrize("device_info", [SAROS_10R])
async def test_disable_and_enable(
    carpet_mode: CarpetModeTrait | None,
    device_info: HomeDataDevice,
    mock_rpc_channel: AsyncMock,
) -> None:
    """Writes send the boost setting with the motor tuning values from the last refresh."""
    assert carpet_mode is not None
    mock_rpc_channel.send_command.return_value = CARPET_MODE_RESPONSE
    await carpet_mode.refresh()
    mock_rpc_channel.send_command.reset_mock()

    await carpet_mode.disable()
    assert not carpet_mode.is_on
    await carpet_mode.enable()
    assert carpet_mode.is_on

    tuning = {"current_integral": 1000, "current_high": 500, "current_low": 1000, "stall_time": 10}
    assert mock_rpc_channel.send_command.call_args_list == [
        call(RoborockCommand.SET_CARPET_MODE, params=[{"enable": 0, **tuning}]),
        call(RoborockCommand.SET_CARPET_MODE, params=[{"enable": 1, **tuning}]),
    ]


@pytest.mark.parametrize("device_info", [SAROS_10R])
async def test_write_requires_refresh(
    carpet_mode: CarpetModeTrait | None,
    device_info: HomeDataDevice,
    mock_rpc_channel: AsyncMock,
) -> None:
    """Writing before the tuning values are loaded raises instead of sending defaults."""
    assert carpet_mode is not None

    with pytest.raises(RoborockException, match="call refresh"):
        await carpet_mode.disable()

    mock_rpc_channel.send_command.assert_not_called()
