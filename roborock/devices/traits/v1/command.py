from typing import Any

from roborock import RoborockCommand
from roborock.data.v1 import RoborockZone
from roborock.protocols.v1_protocol import ParamsType


class CommandTrait:
    """Trait for sending commands to Roborock devices.

    This trait allows sending raw commands directly to the device. It is particularly
    useful for:
    1.  **Cleaning Control**: Sending commands like `app_start`, `app_stop`, `app_pause`,
        or `app_charge` which don't belong to a specific state trait.
    2.  **Unsupported Features**: Accessing device functionality that hasn't been
        mapped to a specific trait yet.

    See `roborock.roborock_typing.RoborockCommand` for a list of available commands.
    """

    def __post_init__(self) -> None:
        """Post-initialization to set up the RPC channel.

        This is called automatically after the dataclass is initialized by the
        device setup code.
        """
        self._rpc_channel = None

    async def clean_zones(self, zones: list[RoborockZone], *, repeat: int = 1) -> None:
        """Start cleaning the given rectangular zones of the current map.

        Zone coordinates are in the device's map coordinate space. `repeat` is
        the number of times each zone is cleaned.
        """
        for zone in zones:
            if zone.x_start == zone.x_end or zone.y_start == zone.y_end:
                raise ValueError(f"Zone must enclose an area: {zone}")
        params = [[zone.x_start, zone.y_start, zone.x_end, zone.y_end, repeat] for zone in zones]
        await self.send(RoborockCommand.APP_ZONED_CLEAN, params=params)

    async def send(self, command: RoborockCommand | str, params: ParamsType = None) -> Any:
        """Send a command to the device.

        Sending a raw command to the device using this method does not update
        the internal state of any other traits. It is the responsibility of the
        caller to ensure that any traits affected by the command are refreshed
        as needed.
        """
        if not self._rpc_channel:
            raise ValueError("Device trait in invalid state")
        return await self._rpc_channel.send_command(command, params=params)
