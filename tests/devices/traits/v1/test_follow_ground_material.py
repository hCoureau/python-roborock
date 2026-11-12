"""Tests for the FollowGroundMaterialTrait class."""

from copy import deepcopy
from unittest.mock import AsyncMock, call

import pytest

from roborock.data import HomeData
from roborock.devices.device import RoborockDevice
from roborock.devices.traits.v1.follow_ground_material import FollowGroundMaterialTrait
from roborock.roborock_typing import RoborockCommand
from tests import mock_data

FLOOR_DIRECTION_FEATURE = "0000000000002841"
NO_FLOOR_DIRECTION_FEATURE = "0000000000002041"


def _home_data(new_feature_set: str) -> HomeData:
    raw = deepcopy(mock_data.HOME_DATA_RAW)
    raw["devices"][0]["newFeatureSet"] = new_feature_set
    return HomeData.from_dict(raw)


@pytest.fixture(name="follow_ground_material")
def follow_ground_material_trait(
    device: RoborockDevice,
    discover_features_fixture: None,
) -> FollowGroundMaterialTrait | None:
    """Return the trait created by feature discovery."""
    assert device.v1_properties
    return device.v1_properties.follow_ground_material


@pytest.mark.parametrize("trait_home_data", [_home_data(NO_FLOOR_DIRECTION_FEATURE)], indirect=True)
async def test_unsupported_without_floor_direction_feature(
    follow_ground_material: FollowGroundMaterialTrait | None,
    trait_home_data: HomeData,
) -> None:
    """The trait is not created when the device does not report floor direction support."""
    assert follow_ground_material is None


@pytest.mark.parametrize("trait_home_data", [_home_data(FLOOR_DIRECTION_FEATURE)], indirect=True)
@pytest.mark.parametrize(("response", "expected"), [({"status": 0}, False), ({"status": 1}, True)])
async def test_refresh(
    follow_ground_material: FollowGroundMaterialTrait | None,
    trait_home_data: HomeData,
    mock_rpc_channel: AsyncMock,
    response: dict[str, int],
    expected: bool,
) -> None:
    """Refreshing reads the setting from the device."""
    assert follow_ground_material is not None
    mock_rpc_channel.send_command.return_value = response

    await follow_ground_material.refresh()

    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.GET_CLEAN_FOLLOW_GROUND_MATERIAL_STATUS)
    assert follow_ground_material.is_on is expected


@pytest.mark.parametrize("trait_home_data", [_home_data(FLOOR_DIRECTION_FEATURE)], indirect=True)
async def test_enable_and_disable(
    follow_ground_material: FollowGroundMaterialTrait | None,
    trait_home_data: HomeData,
    mock_rpc_channel: AsyncMock,
) -> None:
    """Enabling and disabling send the status value and update the trait."""
    assert follow_ground_material is not None

    await follow_ground_material.enable()
    assert follow_ground_material.is_on
    await follow_ground_material.disable()
    assert not follow_ground_material.is_on

    assert mock_rpc_channel.send_command.call_args_list == [
        call(RoborockCommand.SET_CLEAN_FOLLOW_GROUND_MATERIAL_STATUS, params={"status": 1}),
        call(RoborockCommand.SET_CLEAN_FOLLOW_GROUND_MATERIAL_STATUS, params={"status": 0}),
    ]
