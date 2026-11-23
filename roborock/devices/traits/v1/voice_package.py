"""Trait for the voice package selected on the device."""

from dataclasses import dataclass

from roborock.data.containers import RoborockBase
from roborock.devices.traits.v1 import common
from roborock.roborock_typing import RoborockCommand


@dataclass
class VoicePackage(RoborockBase):
    """Voice package metadata reported by `get_current_sound`."""

    sid_in_use: int | None = None
    """ID of the selected voice package."""

    sid_version: int | None = None
    """Version of the selected voice package."""

    sid_in_progress: int | None = None
    """ID of the voice package the device reports as in progress."""

    msg_ver: int | None = None
    location: str | None = None
    bom: str | None = None

    language: str | None = None
    """Language code of the selected voice package (e.g. ``en``)."""


class VoicePackageTrait(VoicePackage, common.V1TraitMixin):
    """Trait for reading the device's voice package metadata."""

    command = RoborockCommand.GET_CURRENT_SOUND
    converter = common.DefaultConverter(VoicePackage)
