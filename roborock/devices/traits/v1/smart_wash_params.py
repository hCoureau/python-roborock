"""Trait for smart wash parameters."""

from roborock.data import RoborockSmartWashMode, SmartWashParams
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

    @property
    def mode(self) -> RoborockSmartWashMode | None:
        """Return when the dock washes the mop, or `unknown` for values without documented meaning.

        The raw `smart_wash` value is kept unchanged.
        """
        if self.smart_wash is None:
            return None
        return RoborockSmartWashMode(self.smart_wash)

    async def set_params(self, mode: RoborockSmartWashMode, wash_interval: int) -> None:
        """Set when the dock washes the mop and the wash interval in seconds.

        Both values are always sent. Writing replaces the current `smart_wash`
        value, including values without documented meaning.
        """
        if mode is RoborockSmartWashMode.unknown:
            raise ValueError("Cannot set an unknown smart wash mode")
        if wash_interval <= 0:
            raise ValueError("Wash interval must be positive")
        await self.rpc_channel.send_command(
            RoborockCommand.SET_SMART_WASH_PARAMS,
            params={"smart_wash": mode.value, "wash_interval": wash_interval},
        )
        await self.refresh()
