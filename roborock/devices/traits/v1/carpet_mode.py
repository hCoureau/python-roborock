"""Trait for the carpet boost setting."""

from dataclasses import asdict, replace

from roborock.data import CarpetMode, CarpetModeSettings
from roborock.devices.traits.v1 import common
from roborock.exceptions import RoborockException
from roborock.roborock_typing import RoborockCommand


class CarpetModeConverter(common.V1TraitDataConverter):
    """Converter for CarpetMode."""

    def convert(self, response: common.V1ResponseData) -> CarpetMode:
        """Parse the response from the device into a CarpetMode."""
        if isinstance(response, list):
            if not response:
                raise ValueError("Empty CarpetMode response")
            response = response[0]
        if not isinstance(response, dict):
            raise ValueError(f"Unexpected CarpetMode response format: {response!r}")
        settings = CarpetModeSettings.from_dict(response)
        if None in asdict(settings).values():
            raise ValueError(f"Incomplete CarpetMode response: {response!r}")
        return CarpetMode(settings=settings)


class CarpetModeTrait(CarpetMode, common.V1TraitMixin, common.RoborockSwitchBase):
    """Trait for turning carpet boost on or off.

    The device expects the motor tuning values with every write, so `enable()`
    and `disable()` send back the values read by the last `refresh()`.
    """

    command = RoborockCommand.GET_CARPET_MODE
    converter = CarpetModeConverter()
    requires_feature = "is_carpet_supported"

    @property
    def is_on(self) -> bool:
        """Return whether carpet boost is enabled."""
        return self.settings is not None and self.settings.enable == 1

    async def enable(self) -> None:
        """Enable carpet boost."""
        await self._set_enable(1)

    async def disable(self) -> None:
        """Disable carpet boost."""
        await self._set_enable(0)

    async def _set_enable(self, enable: int) -> None:
        if self.settings is None:
            raise RoborockException("Carpet mode is not loaded, call refresh() first")
        settings = replace(self.settings, enable=enable)
        await self.rpc_channel.send_command(RoborockCommand.SET_CARPET_MODE, params=[asdict(settings)])
        # Optimistic update to avoid an extra refresh
        self.settings = settings
