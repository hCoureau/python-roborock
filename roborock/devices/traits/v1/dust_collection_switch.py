"""Trait for automatic dust emptying by the dock."""

from roborock.data import DustCollectionSwitchStatus
from roborock.device_features import RoborockDockFeatures
from roborock.devices.traits.v1 import common
from roborock.roborock_typing import RoborockCommand

_STATUS_PARAM = "status"


def _supports_dust_collection_switch(dock_features: RoborockDockFeatures) -> bool:
    return dock_features.is_collectable


class DustCollectionSwitchTrait(DustCollectionSwitchStatus, common.V1TraitMixin, common.RoborockSwitchBase):
    """Trait for turning automatic dust emptying by the dock on or off.

    `0` is off and `1` is the normal emptying frequency. Some docks offer further
    frequencies (for example a "High" level that also empties during cleaning);
    those values are kept in `status`, count as on, and are not written by this trait.
    """

    command = RoborockCommand.GET_DUST_COLLECTION_SWITCH_STATUS
    converter = common.DefaultConverter(DustCollectionSwitchStatus)
    requires_dock_features = _supports_dust_collection_switch

    @property
    def is_on(self) -> bool:
        """Return whether automatic dust emptying is enabled at any frequency."""
        return self.status is not None and self.status != 0

    async def enable(self) -> None:
        """Enable automatic dust emptying at the normal frequency."""
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
