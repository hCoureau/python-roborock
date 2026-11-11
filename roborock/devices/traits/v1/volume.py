from dataclasses import dataclass

from roborock.data.containers import RoborockBase
from roborock.devices.traits.v1 import common
from roborock.exceptions import RoborockParsingException
from roborock.roborock_typing import RoborockCommand


@dataclass
class CurrentSound(RoborockBase):
    """Reported metadata for the selected and in-progress voice packages."""

    sid_in_use: int | None = None
    sid_version: int | None = None
    sid_in_progress: int | None = None
    msg_ver: int | None = None
    location: str | None = None
    bom: str | None = None
    language: str | None = None


@dataclass
class SoundVolume(RoborockBase):
    """Dataclass for sound volume."""

    volume: int | None = None
    """Sound volume level (0-100)."""


class SoundVolumeTrait(SoundVolume, common.V1TraitMixin):
    """Trait for controlling the sound volume of a Roborock device."""

    command = RoborockCommand.GET_SOUND_VOLUME
    converter = common.SingleValueConverter(SoundVolume, "volume")

    async def get_current_sound(self) -> CurrentSound:
        """Read voice-package metadata without changing the cached volume."""
        response = await self.rpc_channel.send_command(RoborockCommand.GET_CURRENT_SOUND)
        try:
            payload = response
            if isinstance(payload, list):
                if len(payload) != 1:
                    raise ValueError("Expected exactly one current sound record")
                payload = payload[0]
            if not isinstance(payload, dict):
                raise ValueError(f"Unexpected CurrentSound response format: {payload!r}")
            return CurrentSound.from_dict(payload)
        except (TypeError, ValueError) as err:
            raise RoborockParsingException(
                trait_name=type(self).__name__,
                command=RoborockCommand.GET_CURRENT_SOUND,
                payload=response,
                inner_error=err,
            ) from err

    async def set_volume(self, volume: int) -> None:
        """Set the sound volume of the device."""
        await self.rpc_channel.send_command(RoborockCommand.CHANGE_SOUND_VOLUME, params=[volume])
        self.volume = volume
