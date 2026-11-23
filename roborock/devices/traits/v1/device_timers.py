"""Trait for the schedules stored on the device and read with `get_timer`.

This is not every schedule: some devices (such as a15 and a27) return an empty list while their schedules
live in the cloud (`UserWebApiClient.get_schedules`, `HomeDataSchedule`) or as server timers.
"""

import logging

from roborock.data import DeviceTimer, DeviceTimerCleanParams, DeviceTimers
from roborock.devices.traits.v1 import common
from roborock.roborock_typing import RoborockCommand

_LOGGER = logging.getLogger(__name__)

_STATES = {"on": True, "off": False}


def _parse_timer(entry: object) -> DeviceTimer:
    """Parse one `[id, state, [cron, [action, *params]]]` entry."""
    match entry:
        case [str() | int() as timer_id, str() as state, [str() as cron, [str() as action, *params], *_], *_]:
            pass
        case _:
            raise ValueError(f"Unexpected timer entry: {entry!r}")
    match params:
        case [dict() as values]:
            clean_params: DeviceTimerCleanParams | None = DeviceTimerCleanParams.from_dict(values)
        case [] | [""]:  # Older firmware sends an empty string.
            clean_params = None
        case _:  # Such as the positional `[fan_power, segments]` the app can send in `set_timer`.
            _LOGGER.debug("Ignoring unrecognised parameters of timer %s: %r", timer_id, params)
            clean_params = None
    return DeviceTimer(
        timer_id=str(timer_id), enabled=_STATES.get(state), cron=cron, action=action, clean_params=clean_params
    )


class DeviceTimersConverter(common.V1TraitDataConverter):
    """Converts `get_timer` responses to DeviceTimers."""

    def convert(self, response: common.V1ResponseData) -> DeviceTimers:
        if not isinstance(response, list):
            raise ValueError(f"Unexpected timer response: {response!r}")
        return DeviceTimers(timers=[_parse_timer(entry) for entry in response])


class DeviceTimersTrait(DeviceTimers, common.V1TraitMixin):
    """Trait for the schedules stored on the device; an empty list does not mean the device has no schedules."""

    command = RoborockCommand.GET_TIMER
    converter = DeviceTimersConverter()

    async def set_enabled(self, timer_id: str, enabled: bool) -> None:
        """Switch a stored schedule on or off, then read the schedules back."""
        await self.rpc_channel.send_command(RoborockCommand.UPD_TIMER, params=[timer_id, "on" if enabled else "off"])
        await self.refresh()
