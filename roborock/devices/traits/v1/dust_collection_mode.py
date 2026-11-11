"""Trait for dust collection mode."""

from roborock.data import DustCollectionMode, RoborockDockDustCollectionModeCode
from roborock.device_features import RoborockDockFeatures
from roborock.devices.traits.v1 import common
from roborock.exceptions import RoborockUnsupportedFeature
from roborock.roborock_typing import RoborockCommand


def _supports_dust_collection_mode(dock_features: RoborockDockFeatures) -> bool:
    return dock_features.is_collectable


class DustCollectionModeTrait(DustCollectionMode, common.V1TraitMixin):
    """Trait for dust collection mode."""

    command = RoborockCommand.GET_DUST_COLLECTION_MODE
    converter = common.DefaultConverter(DustCollectionMode)
    requires_dock_features = _supports_dust_collection_mode

    async def set_mode(self, mode: RoborockDockDustCollectionModeCode) -> None:
        """Set a dust collection mode, then read back the dock's setting.

        Available modes depend on the dock; the enum does not certify support
        for every mode on every collectable dock.
        """
        if mode == RoborockDockDustCollectionModeCode.unknown:
            raise RoborockUnsupportedFeature("Cannot set an unknown dust collection mode")
        await self.rpc_channel.send_command(RoborockCommand.SET_DUST_COLLECTION_MODE, params={"mode": int(mode)})
        await self.refresh()
