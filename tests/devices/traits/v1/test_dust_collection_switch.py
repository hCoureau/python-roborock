"""Tests for the DustCollectionSwitchTrait class."""

from unittest.mock import AsyncMock, call

import pytest

from roborock.data import RoborockDockTypeCode
from roborock.devices.device import RoborockDevice
from roborock.devices.traits.v1.dust_collection_switch import DustCollectionSwitchTrait
from roborock.roborock_typing import RoborockCommand
from tests.devices.traits.v1.helpers import dock_types_with_capability

COLLECTING_DOCK = RoborockDockTypeCode.o4_dock


@pytest.fixture(name="dust_collection_switch")
def dust_collection_switch_trait(
    device: RoborockDevice,
    discover_features_fixture: None,
) -> DustCollectionSwitchTrait | None:
    """Return the trait created by feature discovery."""
    assert device.v1_properties
    return device.v1_properties.dust_collection_switch


@pytest.mark.parametrize(("dock_type_code"), dock_types_with_capability("is_collectable"))
async def test_available_for_collecting_docks(
    dust_collection_switch: DustCollectionSwitchTrait | None,
    dock_type_code: RoborockDockTypeCode,
) -> None:
    """The trait is created for docks that empty the dust bin."""
    assert dust_collection_switch is not None


@pytest.mark.parametrize(("dock_type_code"), dock_types_with_capability("is_collectable", expected=False))
async def test_unsupported_for_other_docks(
    dust_collection_switch: DustCollectionSwitchTrait | None,
    dock_type_code: RoborockDockTypeCode,
) -> None:
    """The trait is not created for docks that cannot empty the dust bin."""
    assert dust_collection_switch is None


@pytest.mark.parametrize(("dock_type_code"), [COLLECTING_DOCK])
@pytest.mark.parametrize(
    ("response", "expected"), [({"status": 1}, True), ({"status": 2}, True), ({"status": 0}, False)]
)
async def test_refresh(
    dust_collection_switch: DustCollectionSwitchTrait | None,
    mock_rpc_channel: AsyncMock,
    dock_type_code: RoborockDockTypeCode,
    response: dict[str, int],
    expected: bool,
) -> None:
    """Refreshing reads the setting from the device."""
    assert dust_collection_switch is not None
    mock_rpc_channel.send_command.return_value = response

    await dust_collection_switch.refresh()

    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.GET_DUST_COLLECTION_SWITCH_STATUS)
    assert dust_collection_switch.is_on is expected
    assert dust_collection_switch.status == response["status"]


@pytest.mark.parametrize(("dock_type_code"), [COLLECTING_DOCK])
async def test_enable_and_disable(
    dust_collection_switch: DustCollectionSwitchTrait | None,
    mock_rpc_channel: AsyncMock,
    dock_type_code: RoborockDockTypeCode,
) -> None:
    """Enabling and disabling send the status value and update the trait."""
    assert dust_collection_switch is not None
    assert not dust_collection_switch.is_on

    await dust_collection_switch.disable()
    assert not dust_collection_switch.is_on
    await dust_collection_switch.enable()
    assert dust_collection_switch.is_on

    assert mock_rpc_channel.send_command.call_args_list == [
        call(RoborockCommand.SET_DUST_COLLECTION_SWITCH_STATUS, params={"status": 0}),
        call(RoborockCommand.SET_DUST_COLLECTION_SWITCH_STATUS, params={"status": 1}),
    ]
