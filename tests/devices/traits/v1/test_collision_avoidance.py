"""Tests for the CollisionAvoidanceTrait class."""

from copy import deepcopy
from unittest.mock import AsyncMock, call

import pytest

from roborock.data import HomeData
from roborock.devices.device import RoborockDevice
from roborock.devices.traits.v1.collision_avoidance import CollisionAvoidanceTrait
from roborock.roborock_typing import RoborockCommand
from tests import mock_data

COLLISION_FEATURE = "0000000008002041"
TWO_LEVEL_COLLISION_FEATURE = "00400000000000000000000008002041"
NO_COLLISION_FEATURE = "0000000000002041"


def _home_data(new_feature_set: str) -> HomeData:
    raw = deepcopy(mock_data.HOME_DATA_RAW)
    raw["devices"][0]["newFeatureSet"] = new_feature_set
    return HomeData.from_dict(raw)


@pytest.fixture(name="collision_avoidance")
def collision_avoidance_trait(
    device: RoborockDevice,
    discover_features_fixture: None,
) -> CollisionAvoidanceTrait | None:
    """Return the trait created by feature discovery."""
    assert device.v1_properties
    return device.v1_properties.collision_avoidance


@pytest.mark.parametrize(
    ("trait_home_data", "expected"),
    [
        (_home_data(COLLISION_FEATURE), True),
        (_home_data(TWO_LEVEL_COLLISION_FEATURE), False),
        (_home_data(NO_COLLISION_FEATURE), False),
    ],
    indirect=["trait_home_data"],
)
async def test_discovery(
    collision_avoidance: CollisionAvoidanceTrait | None,
    trait_home_data: HomeData,
    expected: bool,
) -> None:
    """The switch is only created for devices with on/off collision avoidance."""
    assert (collision_avoidance is not None) is expected


@pytest.mark.parametrize("trait_home_data", [_home_data(COLLISION_FEATURE)], indirect=True)
@pytest.mark.parametrize(("response", "expected"), [({"status": 1}, True), ({"status": 0}, False)])
async def test_refresh(
    collision_avoidance: CollisionAvoidanceTrait | None,
    trait_home_data: HomeData,
    mock_rpc_channel: AsyncMock,
    response: dict[str, int],
    expected: bool,
) -> None:
    """Refreshing reads the setting from the device."""
    assert collision_avoidance is not None
    mock_rpc_channel.send_command.return_value = response

    await collision_avoidance.refresh()

    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.GET_COLLISION_AVOID_STATUS)
    assert collision_avoidance.is_on is expected


@pytest.mark.parametrize("trait_home_data", [_home_data(COLLISION_FEATURE)], indirect=True)
async def test_enable_and_disable(
    collision_avoidance: CollisionAvoidanceTrait | None,
    trait_home_data: HomeData,
    mock_rpc_channel: AsyncMock,
) -> None:
    """Enabling and disabling send the status value and update the trait."""
    assert collision_avoidance is not None

    await collision_avoidance.enable()
    assert collision_avoidance.is_on
    await collision_avoidance.disable()
    assert not collision_avoidance.is_on

    assert mock_rpc_channel.send_command.call_args_list == [
        call(RoborockCommand.SET_COLLISION_AVOID_STATUS, params={"status": 1}),
        call(RoborockCommand.SET_COLLISION_AVOID_STATUS, params={"status": 0}),
    ]
