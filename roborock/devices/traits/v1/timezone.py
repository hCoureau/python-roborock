"""Trait for the robot's timezone setting."""

import re
from dataclasses import dataclass

from roborock.data import RoborockBase
from roborock.devices.traits.v1 import common
from roborock.exceptions import RoborockException
from roborock.roborock_typing import RoborockCommand

# IANA-style syntax only (no whitespace, `..` or leading `/`); the robot decides which names it accepts.
_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z0-9_+-]+(?:/[A-Za-z0-9_+-]+)*")


@dataclass
class RobotTimezone(RoborockBase):
    """The timezone configured on the robot."""

    identifier: str | None = None
    """IANA timezone identifier, e.g. "Europe/Berlin"."""


class TimezoneConverter(common.V1TraitDataConverter):
    """Parse the `["<identifier>"]` response of `get_timezone`."""

    def convert(self, response: common.V1ResponseData) -> RobotTimezone:
        if not isinstance(response, list) or len(response) != 1:
            raise ValueError(f"Unexpected RobotTimezone response format: {response!r}")
        identifier = response[0]
        if not isinstance(identifier, str) or not identifier:
            raise ValueError(f"Unexpected RobotTimezone response format: {response!r}")
        return RobotTimezone(identifier=identifier)


class TimezoneTrait(RobotTimezone, common.V1TraitMixin):
    """Trait for reading and setting the robot's timezone."""

    command = RoborockCommand.GET_TIMEZONE
    converter = TimezoneConverter()

    async def set_timezone(self, identifier: str) -> None:
        """Set the robot's timezone to an IANA timezone identifier."""
        if not _IDENTIFIER_PATTERN.fullmatch(identifier):
            raise ValueError(f"Invalid timezone identifier: {identifier!r}")
        response = await self.rpc_channel.send_command(RoborockCommand.SET_TIMEZONE, params=[identifier])
        # decode_rpc_response normalizes a bare "ok" to {}; other firmware sends ["ok"].
        if response not in ({}, ["ok"]):
            raise RoborockException(f"Command {RoborockCommand.SET_TIMEZONE.value} was not accepted")
        self.identifier = identifier
