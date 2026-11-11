"""Trait for smart wash parameters."""

from roborock.data import SmartWashParams
from roborock.device_features import RoborockDockFeatures
from roborock.devices.traits.v1 import common
from roborock.roborock_typing import RoborockCommand


def _supports_smart_wash_params(dock_features: RoborockDockFeatures) -> bool:
    return dock_features.is_washable


class SmartWashParamsTrait(SmartWashParams, common.V1TraitMixin):
    """Trait for smart wash parameters."""

    command = RoborockCommand.GET_SMART_WASH_PARAMS
    converter = common.DefaultConverter(SmartWashParams)
    requires_dock_features = _supports_smart_wash_params

    async def set_params(self, smart_wash: bool, wash_interval: int) -> None:
        """Set the legacy on/off setting and a positive wash interval in seconds."""
        if wash_interval <= 0:
            raise ValueError("Wash interval must be positive")
        await self.rpc_channel.send_command(
            RoborockCommand.SET_SMART_WASH_PARAMS,
            params={"smart_wash": int(smart_wash), "wash_interval": wash_interval},
        )
        await self.refresh()
