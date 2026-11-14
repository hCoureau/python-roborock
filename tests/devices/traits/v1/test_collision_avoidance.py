"""Tests for the collision avoidance traits."""

from copy import deepcopy
from unittest.mock import AsyncMock, call

import pytest

from roborock.data import CollisionAvoidanceMode, HomeData
from roborock.devices.device import RoborockDevice
from roborock.devices.traits.v1.collision_avoidance import CollisionAvoidanceModeTrait, CollisionAvoidanceTrait
from roborock.devices.traits.v1.common import RoborockSwitchBase
from roborock.exceptions import RoborockException
from roborock.roborock_typing import RoborockCommand
from tests import mock_data

COLLISION_FEATURE = "0000000008002041"
TWO_LEVEL_COLLISION_FEATURE = "00400000000000000000000008002041"
TWO_LEVEL_ONLY_FEATURE = "00400000000000000000000000002041"
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


@pytest.fixture(name="collision_avoidance_mode")
def collision_avoidance_mode_trait(
    device: RoborockDevice,
    discover_features_fixture: None,
) -> CollisionAvoidanceModeTrait | None:
    """Return the two-level trait created by feature discovery."""
    assert device.v1_properties
    return device.v1_properties.collision_avoidance_mode


@pytest.mark.parametrize(
    ("trait_home_data", "expected_switch", "expected_mode"),
    [
        (_home_data(COLLISION_FEATURE), True, False),
        (_home_data(TWO_LEVEL_COLLISION_FEATURE), False, True),
        (_home_data(TWO_LEVEL_ONLY_FEATURE), False, False),
        (_home_data(NO_COLLISION_FEATURE), False, False),
    ],
    indirect=["trait_home_data"],
)
async def test_discovery(
    collision_avoidance: CollisionAvoidanceTrait | None,
    collision_avoidance_mode: CollisionAvoidanceModeTrait | None,
    trait_home_data: HomeData,
    expected_switch: bool,
    expected_mode: bool,
) -> None:
    """Devices get at most one of the switch and the two-level mode trait."""
    assert (collision_avoidance is not None) is expected_switch
    assert (collision_avoidance_mode is not None) is expected_mode


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


@pytest.mark.parametrize("trait_home_data", [_home_data(TWO_LEVEL_COLLISION_FEATURE)], indirect=True)
@pytest.mark.parametrize(
    ("response", "expected_status", "expected_mode"),
    [
        ({"status": 1}, 1, CollisionAvoidanceMode.HIGH_COVERAGE),
        ({"status": 2}, 2, CollisionAvoidanceMode.LESS_COLLISION),
        ({"status": 0}, 0, None),
        ({"status": 3}, 3, None),
        ([{"status": 2}], 2, CollisionAvoidanceMode.LESS_COLLISION),
    ],
)
async def test_mode_refresh(
    collision_avoidance_mode: CollisionAvoidanceModeTrait | None,
    trait_home_data: HomeData,
    mock_rpc_channel: AsyncMock,
    response: dict[str, int] | list[dict[str, int]],
    expected_status: int,
    expected_mode: CollisionAvoidanceMode | None,
) -> None:
    """Refreshing reads the raw level and decodes known modes."""
    assert collision_avoidance_mode is not None
    mock_rpc_channel.send_command.return_value = response

    await collision_avoidance_mode.refresh()

    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.GET_COLLISION_AVOID_STATUS)
    assert collision_avoidance_mode.status == expected_status
    assert collision_avoidance_mode.mode is expected_mode


@pytest.mark.parametrize("trait_home_data", [_home_data(TWO_LEVEL_COLLISION_FEATURE)], indirect=True)
async def test_mode_refresh_failure_keeps_previous_value(
    collision_avoidance_mode: CollisionAvoidanceModeTrait | None,
    trait_home_data: HomeData,
    mock_rpc_channel: AsyncMock,
) -> None:
    """A failed refresh leaves the last known mode in place."""
    assert collision_avoidance_mode is not None
    assert collision_avoidance_mode.mode is None
    mock_rpc_channel.send_command.return_value = {"status": 2}
    await collision_avoidance_mode.refresh()

    mock_rpc_channel.send_command.side_effect = RoborockException("Communication error")
    with pytest.raises(RoborockException, match="Communication error"):
        await collision_avoidance_mode.refresh()

    assert collision_avoidance_mode.status == 2
    assert collision_avoidance_mode.mode is CollisionAvoidanceMode.LESS_COLLISION


@pytest.mark.parametrize("trait_home_data", [_home_data(TWO_LEVEL_COLLISION_FEATURE)], indirect=True)
async def test_mode_is_read_only(
    collision_avoidance_mode: CollisionAvoidanceModeTrait | None,
    trait_home_data: HomeData,
) -> None:
    """The two-level trait exposes no way to change the setting."""
    assert collision_avoidance_mode is not None
    assert not isinstance(collision_avoidance_mode, RoborockSwitchBase)
    for name in ("enable", "disable", "set_mode"):
        assert not hasattr(collision_avoidance_mode, name)
