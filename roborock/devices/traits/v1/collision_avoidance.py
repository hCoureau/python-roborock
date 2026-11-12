"""Trait for the collision-avoidance navigation setting.

The same value is also reported as `collision_avoid_status` in the status
trait; refresh both when both are displayed.
"""

from roborock.data import CollisionAvoidStatus
from roborock.devices.traits.v1 import common
from roborock.roborock_typing import RoborockCommand

_STATUS_PARAM = "status"


class CollisionAvoidanceTrait(CollisionAvoidStatus, common.V1TraitMixin, common.RoborockSwitchBase):
    """Trait for turning collision-avoidance navigation on or off.

    Only created for devices that report collision avoidance without the
    two-level option, because the values used by two-level devices are not
    documented.
    """

    command = RoborockCommand.GET_COLLISION_AVOID_STATUS
    converter = common.DefaultConverter(CollisionAvoidStatus)
    requires_feature = "is_avoid_collision_supported"

    @property
    def is_on(self) -> bool:
        """Return whether collision avoidance is enabled."""
        return self.status == 1

    async def enable(self) -> None:
        """Enable collision avoidance."""
        await self.rpc_channel.send_command(RoborockCommand.SET_COLLISION_AVOID_STATUS, params={_STATUS_PARAM: 1})
        self.status = 1

    async def disable(self) -> None:
        """Disable collision avoidance."""
        await self.rpc_channel.send_command(RoborockCommand.SET_COLLISION_AVOID_STATUS, params={_STATUS_PARAM: 0})
        self.status = 0
