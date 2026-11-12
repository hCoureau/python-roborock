"""Trait for schedules stored on the device (`get_timer`).

Some devices keep their schedules elsewhere (for example in the cloud), so an
empty list only means that the device reports no local schedules.
"""

from roborock.data import DeviceTimer, DeviceTimers
from roborock.devices.traits.v1 import common
from roborock.roborock_typing import RoborockCommand


def _parse_timer(entry: object) -> DeviceTimer:
    """Parse one `[id, state, [cron, [command, params]]]` entry."""
    if not isinstance(entry, list) or len(entry) < 3:
        raise ValueError(f"Unexpected timer entry: {entry!r}")
    timer_id, state, schedule = entry[0], entry[1], entry[2]
    if not isinstance(timer_id, str | int) or isinstance(timer_id, bool) or not isinstance(state, str):
        raise ValueError(f"Unexpected timer entry: {entry!r}")
    if not isinstance(schedule, list) or not schedule or not isinstance(schedule[0], str):
        raise ValueError(f"Unexpected timer schedule: {entry!r}")
    action_spec = schedule[1] if len(schedule) > 1 else None
    if not isinstance(action_spec, list) or len(action_spec) < 2 or not isinstance(action_spec[0], str):
        raise ValueError(f"Unexpected timer action: {entry!r}")
    action_params = action_spec[1]
    if not isinstance(action_params, str | dict):
        raise ValueError(f"Unexpected timer action parameters: {entry!r}")
    return DeviceTimer(
        timer_id=str(timer_id),
        state=state,
        cron=schedule[0],
        action=action_spec[0],
        action_params=action_params,
    )


class DeviceTimersConverter(common.V1TraitDataConverter):
    """Converts `get_timer` responses to DeviceTimers."""

    def convert(self, response: common.V1ResponseData) -> DeviceTimers:
        if not isinstance(response, list):
            raise ValueError(f"Unexpected timer response: {response!r}")
        return DeviceTimers(timers=[_parse_timer(entry) for entry in response])


class TimersTrait(DeviceTimers, common.V1TraitMixin):
    """Trait for reading schedules stored on the device and switching them on or off."""

    command = RoborockCommand.GET_TIMER
    converter = DeviceTimersConverter()

    async def set_enabled(self, timer_id: str, enabled: bool) -> None:
        """Switch a stored schedule on or off, then read the schedules back.

        Switching a schedule on lets it start its command (normally a clean) at the
        next scheduled time without further confirmation.
        """
        await self.rpc_channel.send_command(RoborockCommand.UPD_TIMER, params=[timer_id, "on" if enabled else "off"])
        await self.refresh()
