"""Explicit access to the robot's native timezone setting."""

from dataclasses import dataclass

from roborock.data import RoborockBase
from roborock.devices.traits.v1 import common
from roborock.roborock_typing import RoborockCommand


@dataclass
class RobotTimezone(RoborockBase):
    """The robot's reported timezone, distinct from app and host settings."""

    identifier: str | None = None
    """Last explicitly reported TZ/IANA identifier, or None before a read or after an accepted write."""


class TimezoneConverter(common.V1TraitDataConverter):
    """Convert the singleton string response without coercion or fallbacks."""

    def convert(self, response: common.V1ResponseData) -> RobotTimezone:
        """Return the robot's identifier verbatim."""
        if (
            not isinstance(response, list)
            or len(response) != 1
            or not isinstance(response[0], str)
            or not response[0].strip()
        ):
            raise ValueError("Expected a singleton list containing a nonempty timezone string")
        return RobotTimezone(identifier=response[0])


class TimezoneTrait(RobotTimezone, common.V1TraitMixin):
    """Read and set the robot's timezone through explicit calls.

    Refresh failures preserve the last report. Callers should sequence writes
    and readback; concurrent calls and changes by other clients can leave it stale.
    """

    command = RoborockCommand.GET_TIMEZONE
    converter = TimezoneConverter()

    async def set_timezone(self, identifier: str) -> None:
        """Set a firmware-accepted identifier, then invalidate the cached report.

        This does not read back or change timers. A failed request preserves the
        previous report, but a timeout can leave the actual write outcome unknown.
        """
        if not identifier.strip():
            raise ValueError("Timezone identifier must not be empty or whitespace")
        await self.rpc_channel.send_command(RoborockCommand.SET_TIMEZONE, params=[identifier])
        self.identifier = None
