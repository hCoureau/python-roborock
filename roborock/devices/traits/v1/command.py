from typing import Any

from roborock import RoborockCommand
from roborock.data import DockInfo
from roborock.exceptions import RoborockParsingException
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

    async def get_dock_info(self) -> DockInfo:
        """Read opaque dock version metadata on demand, excluding the serial number."""
        response = await self.send(RoborockCommand.GET_DOCK_INFO)
        context: dict[str, Any] = {"response": "[REDACTED]", "response_type": type(response).__name__}
        if isinstance(response, list):
            context["response_length"] = len(response)
        try:
            if isinstance(response, list):
                if len(response) != 1:
                    raise ValueError("Expected exactly one dock info object")
                response = response[0]
            if not isinstance(response, dict):
                raise TypeError("Expected a dock info object")
            version = response.get("version")
            if version is not None and not isinstance(version, str):
                context["version_type"] = type(version).__name__
                raise TypeError("Expected a string or null dock version")
            context = {"version": version}
            return DockInfo(version=version)
        except (TypeError, ValueError) as err:
            raise RoborockParsingException(
                trait_name=self.__class__.__name__,
                command=RoborockCommand.GET_DOCK_INFO,
                payload=context,
                inner_error=err,
            ) from err
