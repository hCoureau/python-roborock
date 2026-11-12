"""Trait for automatic dust emptying by the dock."""

from roborock.data import DustCollectionSwitchStatus
from roborock.device_features import RoborockDockFeatures
from roborock.devices.traits.v1 import common
from roborock.roborock_typing import RoborockCommand

_STATUS_PARAM = "status"


def _supports_dust_collection_switch(dock_features: RoborockDockFeatures) -> bool:
    return dock_features.is_collectable


class DustCollectionSwitchTrait(DustCollectionSwitchStatus, common.V1TraitMixin, common.RoborockSwitchBase):
    """Trait for turning automatic dust emptying by the dock on or off."""

    command = RoborockCommand.GET_DUST_COLLECTION_SWITCH_STATUS
    converter = common.DefaultConverter(DustCollectionSwitchStatus)
    requires_dock_features = _supports_dust_collection_switch

    @property
    def is_on(self) -> bool:
        """Return whether automatic dust emptying is enabled."""
        return self.status == 1

    async def enable(self) -> None:
        """Enable automatic dust emptying."""
        await self.rpc_channel.send_command(
            RoborockCommand.SET_DUST_COLLECTION_SWITCH_STATUS, params={_STATUS_PARAM: 1}
        )
        self.status = 1

    async def disable(self) -> None:
        """Disable automatic dust emptying."""
        await self.rpc_channel.send_command(
            RoborockCommand.SET_DUST_COLLECTION_SWITCH_STATUS, params={_STATUS_PARAM: 0}
        )
        self.status = 0
