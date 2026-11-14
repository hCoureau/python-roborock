"""Tests for the RoutinesTrait."""

from unittest.mock import AsyncMock

import pytest

from roborock.data.containers import HomeDataScene
from roborock.devices.device import RoborockDevice
from roborock.devices.traits.v1.routines import RoutinesTrait
from tests.mock_data import HOME_DATA_SCENES_RAW


@pytest.fixture(name="routines_trait")
def routines_trait_fixture(device: RoborockDevice) -> RoutinesTrait:
    """Fixture for the routines trait."""
    assert device.v1_properties
    return device.v1_properties.routines


async def test_get_routines(routines_trait: RoutinesTrait, web_api_client: AsyncMock) -> None:
    """Test getting routines."""
    web_api_client.get_routines.return_value = [HomeDataScene(id=1, name="test_scene")]
    routines = await routines_trait.get_routines()
    assert len(routines) == 1
    assert routines[0].name == "test_scene"
    web_api_client.get_routines.assert_called_once()


async def test_get_routines_enabled_and_type(routines_trait: RoutinesTrait, web_api_client: AsyncMock) -> None:
    """Test that routines expose enabled and type, which are optional in the payload."""
    web_api_client.get_routines.return_value = [
        HomeDataScene.from_dict(HOME_DATA_SCENES_RAW[0]),
        HomeDataScene.from_dict({"id": 2, "name": "No extra fields"}),
    ]
    routines = await routines_trait.get_routines()
    assert [(r.id, r.enabled, r.type) for r in routines] == [
        (1234567, True, "WORKFLOW"),
        (2, None, None),
    ]


async def test_execute_routine(routines_trait: RoutinesTrait, web_api_client: AsyncMock) -> None:
    """Test executing a routine."""
    await routines_trait.execute_routine(1)
    web_api_client.execute_routine.assert_called_once_with(1)
