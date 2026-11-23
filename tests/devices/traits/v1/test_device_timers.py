"""Tests for the DeviceTimersTrait class."""

from unittest.mock import AsyncMock, call

import pytest

from roborock.data import DeviceTimer, DeviceTimerCleanParams
from roborock.devices.device import RoborockDevice
from roborock.devices.traits.v1.device_timers import DeviceTimersTrait
from roborock.exceptions import RoborockParsingException
from roborock.roborock_typing import RoborockCommand

# Legacy layout documented by python-miio.
LEGACY_TIMER = ["1488667794112", "off", ["49 22 * * 6", ["start_clean", ""]]]
# Newer layout with clean settings, as the app sends them in `set_timer`.
SEGMENT_TIMER = [
    "1700000000000",
    "on",
    ["30 9 * * 1,3,5", ["start_clean", {"segments": "0", "repeat": 1, "fan_power": 102, "map_index": -1}]],
]


def _timer(state: object = "on", action: object = None) -> list:
    """Return a `get_timer` entry with the given state and action."""
    return ["1700000000000", state, ["0 8 * * *", ["start_clean", ""] if action is None else action]]


@pytest.fixture(name="device_timers")
def device_timers_trait(device: RoborockDevice) -> DeviceTimersTrait:
    """Return the device timers trait."""
    assert device.v1_properties
    return device.v1_properties.device_timers


async def test_device_timers_before_refresh(device_timers: DeviceTimersTrait) -> None:
    """No schedules are reported before the first refresh."""
    assert device_timers.timers is None


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ([], []),
        (
            [LEGACY_TIMER, SEGMENT_TIMER],
            [
                DeviceTimer(timer_id="1488667794112", enabled=False, cron="49 22 * * 6", action="start_clean"),
                DeviceTimer(
                    timer_id="1700000000000",
                    enabled=True,
                    cron="30 9 * * 1,3,5",
                    action="start_clean",
                    clean_params=DeviceTimerCleanParams(segments="0", repeat=1, fan_power=102, map_index=-1),
                ),
            ],
        ),
        (
            [[1700000000000, "on", ["0 8 * * *", ["start_clean", ""]]]],
            [DeviceTimer(timer_id="1700000000000", enabled=True, cron="0 8 * * *", action="start_clean")],
        ),
    ],
    ids=["empty", "legacy-and-segment", "int-id"],
)
async def test_refresh(
    device_timers: DeviceTimersTrait, mock_rpc_channel: AsyncMock, response: list, expected: list[DeviceTimer]
) -> None:
    """Timer entries are parsed into schedules."""
    mock_rpc_channel.send_command.return_value = response

    await device_timers.refresh()

    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.GET_TIMER)
    assert device_timers.timers == expected


@pytest.mark.parametrize(
    ("state", "enabled"),
    [("on", True), ("off", False), ("paused", None)],
    ids=["on", "off", "unknown"],
)
async def test_refresh_state(
    device_timers: DeviceTimersTrait, mock_rpc_channel: AsyncMock, state: str, enabled: bool | None
) -> None:
    """Only `on` and `off` map to a known state; anything else is reported as unknown."""
    mock_rpc_channel.send_command.return_value = [_timer(state=state)]

    await device_timers.refresh()

    assert device_timers.timers is not None
    assert device_timers.timers[0].enabled is enabled


@pytest.mark.parametrize(
    "action",
    [
        ["start_clean", 104, "16,17"],
        ["start_clean", 104],
        ["start_clean"],
        ["start_clean", 5],
    ],
    ids=["positional-segments", "positional-fan-power", "no-params", "scalar-params"],
)
async def test_refresh_unrecognised_params(
    device_timers: DeviceTimersTrait, mock_rpc_channel: AsyncMock, action: list
) -> None:
    """Unrecognised action parameters drop the clean settings without failing the other entries."""
    mock_rpc_channel.send_command.return_value = [_timer(action=action), LEGACY_TIMER]

    await device_timers.refresh()

    assert device_timers.timers == [
        DeviceTimer(timer_id="1700000000000", enabled=True, cron="0 8 * * *", action="start_clean"),
        DeviceTimer(timer_id="1488667794112", enabled=False, cron="49 22 * * 6", action="start_clean"),
    ]


@pytest.mark.parametrize(
    "response",
    [
        {"timers": []},
        ["1700000000000"],
        [["1700000000000", "on"]],
        [["1700000000000", "on", "0 8 * * *"]],
        [["1700000000000", "on", [8, ["start_clean", ""]]]],
        [["1700000000000", "on", ["0 8 * * *", "start_clean"]]],
        [["1700000000000", "on", ["0 8 * * *", []]]],
        [["1700000000000", "on", ["0 8 * * *", [5, ""]]]],
        [["1700000000000", 1, ["0 8 * * *", ["start_clean", ""]]]],
        [[None, "on", ["0 8 * * *", ["start_clean", ""]]]],
    ],
)
async def test_refresh_malformed(
    device_timers: DeviceTimersTrait, mock_rpc_channel: AsyncMock, response: object
) -> None:
    """Malformed responses raise a parsing error and keep the previous schedules."""
    mock_rpc_channel.send_command.return_value = [LEGACY_TIMER]
    await device_timers.refresh()
    mock_rpc_channel.send_command.return_value = response

    with pytest.raises(RoborockParsingException):
        await device_timers.refresh()

    assert device_timers.timers is not None
    assert [timer.timer_id for timer in device_timers.timers] == ["1488667794112"]


@pytest.mark.parametrize(("enabled", "state"), [(True, "on"), (False, "off")])
async def test_set_enabled(
    device_timers: DeviceTimersTrait, mock_rpc_channel: AsyncMock, enabled: bool, state: str
) -> None:
    """Switching a schedule sends upd_timer and reads the schedules back."""
    mock_rpc_channel.send_command.side_effect = [["ok"], [[LEGACY_TIMER[0], state, LEGACY_TIMER[2]]]]

    await device_timers.set_enabled("1488667794112", enabled)

    assert mock_rpc_channel.send_command.call_args_list == [
        call(RoborockCommand.UPD_TIMER, params=["1488667794112", state]),
        call(RoborockCommand.GET_TIMER),
    ]
    assert device_timers.timers is not None
    assert device_timers.timers[0].enabled is enabled
