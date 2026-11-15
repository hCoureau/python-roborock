"""Tests for the FollowGroundMaterialTrait class."""

from unittest.mock import AsyncMock, call

import pytest

from roborock.data import HomeDataDevice
from roborock.devices.device import RoborockDevice
from roborock.devices.traits.v1.follow_ground_material import FollowGroundMaterialTrait
from roborock.roborock_typing import RoborockCommand
from tests import mock_data

# The suite's default device (S7 MaxV) does not report is_support_floor_direction; the Saros 10R does.
SAROS_10R = mock_data.DEVICE_PRODUCT_PAIRS["home_data_device_saros_10r.json"][0]


@pytest.fixture(name="follow_ground_material")
def follow_ground_material_trait(
    device: RoborockDevice,
    discover_features_fixture: None,
) -> FollowGroundMaterialTrait | None:
    """Return the trait created by feature discovery."""
    assert device.v1_properties
    return device.v1_properties.follow_ground_material


async def test_unsupported_without_floor_direction_feature(
    follow_ground_material: FollowGroundMaterialTrait | None,
) -> None:
    """The trait is not created when the device does not report floor direction support."""
    assert follow_ground_material is None


@pytest.mark.parametrize("device_info", [SAROS_10R])
@pytest.mark.parametrize(("response", "expected"), [({"status": 0}, False), ({"status": 1}, True)])
async def test_refresh(
    follow_ground_material: FollowGroundMaterialTrait | None,
    device_info: HomeDataDevice,
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


@pytest.mark.parametrize("device_info", [SAROS_10R])
async def test_enable_and_disable(
    follow_ground_material: FollowGroundMaterialTrait | None,
    device_info: HomeDataDevice,
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
