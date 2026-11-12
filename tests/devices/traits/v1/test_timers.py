"""Tests for the TimersTrait class."""

from unittest.mock import AsyncMock, call

import pytest

from roborock.data import DeviceTimer
from roborock.devices.device import RoborockDevice
from roborock.devices.traits.v1.timers import TimersTrait
from roborock.exceptions import RoborockParsingException
from roborock.roborock_typing import RoborockCommand

# Legacy layout documented by python-miio.
LEGACY_TIMER = ["1488667794112", "off", ["49 22 * * 6", ["start_clean", ""]]]
# Newer layout with an object of clean parameters, as sent by the app in set_timer.
SEGMENT_TIMER = [
    "1700000000000",
    "on",
    ["30 9 * * 1,3,5", ["start_clean", {"segments": "0", "repeat": 1, "fan_power": 102, "map_index": -1}]],
]


@pytest.fixture(name="timers")
def timers_trait(device: RoborockDevice) -> TimersTrait:
    """Return the timers trait."""
    assert device.v1_properties
    return device.v1_properties.timers


async def test_timers_before_refresh(timers: TimersTrait) -> None:
    """No schedules are reported before the first refresh."""
    assert timers.timers is None


async def test_refresh_empty(timers: TimersTrait, mock_rpc_channel: AsyncMock) -> None:
    """An empty response means the device reports no stored schedules."""
    mock_rpc_channel.send_command.return_value = []

    await timers.refresh()

    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.GET_TIMER)
    assert timers.timers == []


async def test_refresh_parses_entries(timers: TimersTrait, mock_rpc_channel: AsyncMock) -> None:
    """Both the legacy and the newer entry layouts are parsed."""
    mock_rpc_channel.send_command.return_value = [LEGACY_TIMER, SEGMENT_TIMER]

    await timers.refresh()

    assert timers.timers == [
        DeviceTimer(timer_id="1488667794112", state="off", cron="49 22 * * 6", action="start_clean", action_params=""),
        DeviceTimer(
            timer_id="1700000000000",
            state="on",
            cron="30 9 * * 1,3,5",
            action="start_clean",
            action_params={"segments": "0", "repeat": 1, "fan_power": 102, "map_index": -1},
        ),
    ]
    assert [timer.enabled for timer in timers.timers] == [False, True]


async def test_refresh_keeps_unknown_state(timers: TimersTrait, mock_rpc_channel: AsyncMock) -> None:
    """An unexpected state string is preserved and reported as not enabled."""
    mock_rpc_channel.send_command.return_value = [[1700000000000, "paused", ["0 8 * * *", ["start_clean", ""]]]]

    await timers.refresh()

    assert timers.timers == [
        DeviceTimer(timer_id="1700000000000", state="paused", cron="0 8 * * *", action="start_clean", action_params="")
    ]
    assert not timers.timers[0].enabled


@pytest.mark.parametrize(
    "response",
    [
        {"timers": []},
        [["1700000000000", "on"]],
        [["1700000000000", "on", "0 8 * * *"]],
        [["1700000000000", "on", [8, ["start_clean", ""]]]],
        [["1700000000000", "on", ["0 8 * * *", "start_clean"]]],
        [["1700000000000", "on", ["0 8 * * *"]]],
        [["1700000000000", "on", ["0 8 * * *", []]]],
        [["1700000000000", "on", ["0 8 * * *", [5, ""]]]],
        [["1700000000000", "on", ["0 8 * * *", ["start_clean"]]]],
        [["1700000000000", "on", ["0 8 * * *", ["start_clean", 5]]]],
        [LEGACY_TIMER, ["1700000000000", "on"]],
        [[None, "on", ["0 8 * * *", ["start_clean", ""]]]],
    ],
)
async def test_refresh_malformed(timers: TimersTrait, mock_rpc_channel: AsyncMock, response: object) -> None:
    """Malformed responses raise a parsing error and keep the previous schedules."""
    mock_rpc_channel.send_command.return_value = [LEGACY_TIMER]
    await timers.refresh()
    mock_rpc_channel.send_command.return_value = response

    with pytest.raises(RoborockParsingException):
        await timers.refresh()

    assert timers.timers is not None
    assert [timer.timer_id for timer in timers.timers] == ["1488667794112"]


@pytest.mark.parametrize(("enabled", "state"), [(True, "on"), (False, "off")])
async def test_set_enabled(timers: TimersTrait, mock_rpc_channel: AsyncMock, enabled: bool, state: str) -> None:
    """Switching a schedule sends upd_timer and reads the schedules back."""
    mock_rpc_channel.send_command.side_effect = [["ok"], [[LEGACY_TIMER[0], state, LEGACY_TIMER[2]]]]

    await timers.set_enabled("1488667794112", enabled)

    assert mock_rpc_channel.send_command.call_args_list == [
        call(RoborockCommand.UPD_TIMER, params=["1488667794112", state]),
        call(RoborockCommand.GET_TIMER),
    ]
    assert timers.timers is not None
    assert timers.timers[0].enabled is enabled
