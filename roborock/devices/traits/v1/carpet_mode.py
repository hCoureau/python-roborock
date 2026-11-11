"""Carpet boost control with preserved legacy motor tuning."""

import asyncio
from dataclasses import dataclass, replace

from roborock.data import RoborockBase
from roborock.data.v1.v1_containers import CarpetModeSettings
from roborock.devices.traits.v1 import common
from roborock.exceptions import RoborockParsingException, RoborockUnsupportedFeature
from roborock.roborock_typing import RoborockCommand

_SETTING_FIELDS = ("enable", "current_integral", "current_high", "current_low", "stall_time")


def _parse_settings(response: common.V1ResponseData) -> tuple[CarpetModeSettings, bool]:
    """Parse complete legacy settings and determine whether writing is safe."""
    if isinstance(response, list):
        if len(response) != 1:
            raise ValueError("Expected exactly one carpet mode settings object")
        response = response[0]
    if not isinstance(response, dict):
        raise TypeError("Expected a carpet mode settings object")
    for name in _SETTING_FIELDS:
        if name not in response:
            raise ValueError(f"Missing carpet mode setting: {name}")
        if type(response[name]) is not int:
            raise TypeError(f"Carpet mode setting {name} must be an integer")
    settings = CarpetModeSettings(
        enable=response["enable"],
        current_integral=response["current_integral"],
        current_high=response["current_high"],
        current_low=response["current_low"],
        stall_time=response["stall_time"],
    )
    return settings, set(response) == set(_SETTING_FIELDS) and settings.enable in (0, 1)


@dataclass
class CarpetModeTrait(RoborockBase, common.V1TraitMixin, common.RoborockSwitchBase):
    """Read carpet boost settings and toggle boost without changing tuning."""

    settings: CarpetModeSettings | None = None

    command = RoborockCommand.GET_CARPET_MODE
    requires_feature = "is_carpet_supported"

    def __post_init__(self) -> None:
        common.V1TraitMixin.__init__(self)
        self._write_lock = asyncio.Lock()
        self._legacy_schema_writable = False

    @property
    def is_on(self) -> bool:
        """Return whether carpet boost is reported enabled."""
        return self.settings is not None and self.settings.enable == 1

    async def refresh(self) -> None:
        """Read complete settings, preserving prior state if the read fails."""
        response = await self.rpc_channel.send_command(self.command)
        try:
            settings, writable = _parse_settings(response)
        except (TypeError, ValueError) as err:
            raise RoborockParsingException(
                trait_name=type(self).__name__,
                command=self.command,
                payload=response,
                inner_error=err,
            ) from err
        self.settings = settings
        self._legacy_schema_writable = writable

    async def enable(self) -> None:
        """Enable carpet boost and read back the device settings."""
        await self._set_enabled(True)

    async def disable(self) -> None:
        """Disable carpet boost and read back the device settings."""
        await self._set_enabled(False)

    async def _set_enabled(self, enabled: bool) -> None:
        async with self._write_lock:
            await self.refresh()
            if not self._legacy_schema_writable:
                raise RoborockUnsupportedFeature(
                    "Carpet boost writes require the known five-field legacy schema with enable 0 or 1"
                )
            assert self.settings is not None
            settings = replace(self.settings, enable=int(enabled))
            await self.rpc_channel.send_command(
                RoborockCommand.SET_CARPET_MODE,
                params=[
                    {
                        "enable": settings.enable,
                        "current_integral": settings.current_integral,
                        "current_high": settings.current_high,
                        "current_low": settings.current_low,
                        "stall_time": settings.stall_time,
                    }
                ],
            )
            await self.refresh()
