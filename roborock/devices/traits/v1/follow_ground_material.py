"""Trait for cleaning along the direction of the floor material."""

from roborock.data import FollowGroundMaterialStatus
from roborock.devices.traits.v1 import common
from roborock.roborock_typing import RoborockCommand

_STATUS_PARAM = "status"


class FollowGroundMaterialTrait(FollowGroundMaterialStatus, common.V1TraitMixin, common.RoborockSwitchBase):
    """Trait for cleaning along the floor material direction, such as wood grain."""

    command = RoborockCommand.GET_CLEAN_FOLLOW_GROUND_MATERIAL_STATUS
    converter = common.DefaultConverter(FollowGroundMaterialStatus)
    requires_feature = "is_support_floor_direction"

    @property
    def is_on(self) -> bool:
        """Return whether cleaning follows the floor material direction."""
        return self.status == 1

    async def enable(self) -> None:
        """Clean along the floor material direction."""
        await self.rpc_channel.send_command(
            RoborockCommand.SET_CLEAN_FOLLOW_GROUND_MATERIAL_STATUS, params={_STATUS_PARAM: 1}
        )
        self.status = 1

    async def disable(self) -> None:
        """Stop cleaning along the floor material direction."""
        await self.rpc_channel.send_command(
            RoborockCommand.SET_CLEAN_FOLLOW_GROUND_MATERIAL_STATUS, params={_STATUS_PARAM: 0}
        )
        self.status = 0
