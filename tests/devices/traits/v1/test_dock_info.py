"""Tests for the DockInfoTrait class."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from roborock.data import RoborockDockTypeCode
from roborock.devices.device import RoborockDevice
from roborock.devices.traits.v1.dock_info import DockInfoTrait
from roborock.exceptions import RoborockParsingException
from roborock.roborock_typing import RoborockCommand
from tests.devices.traits.v1.helpers import dock_types_with_capability

DOCK_INFO_DOCK = RoborockDockTypeCode.f1_dock

# Response shape observed on a Qrevo 2 Pro Series (roborock.vacuum.a294); serial number replaced.
SERIAL = "SYNTHETICSN0123"
DOCK_INFO_DATA = {"sn": SERIAL, "version": "0060"}


@pytest.fixture(name="dock_info")
def dock_info_trait(device: RoborockDevice, discover_features_fixture: None) -> DockInfoTrait | None:
    """Return the dock info trait after feature discovery."""
    assert device.v1_properties
    return device.v1_properties.dock_info


@pytest.mark.parametrize("dock_type_code", dock_types_with_capability("is_dock_info_supported"))
async def test_dock_info_available(
    dock_info: DockInfoTrait | None, mock_rpc_channel: AsyncMock, dock_type_code: RoborockDockTypeCode
) -> None:
    """The trait is discovered for supported docks without sending a command."""
    assert dock_info is not None
    assert dock_info.version is None
    mock_rpc_channel.send_command.assert_not_called()


@pytest.mark.parametrize(
    "dock_type_code", [None, *dock_types_with_capability("is_dock_info_supported", expected=False)]
)
async def test_unsupported_dock_info(dock_info: DockInfoTrait | None, dock_type_code: RoborockDockTypeCode) -> None:
    """The trait is not available without a dock or for other dock types."""
    assert dock_info is None


@pytest.mark.parametrize("dock_type_code", [DOCK_INFO_DOCK])
@pytest.mark.parametrize(
    ("response", "expected_version"),
    [
        (DOCK_INFO_DATA, "0060"),
        ([DOCK_INFO_DATA], "0060"),
        ({"sn": SERIAL}, None),
        ({"sn": SERIAL, "version": None}, None),
        ({"sn": SERIAL, "version": "None"}, None),
        ({"sn": SERIAL, "version": 60}, "60"),
    ],
)
async def test_refresh(
    dock_info: DockInfoTrait | None,
    mock_rpc_channel: AsyncMock,
    dock_type_code: RoborockDockTypeCode,
    response: Any,
    expected_version: str | None,
) -> None:
    """Refreshing reads the dock version and does not keep the serial number."""
    assert dock_info is not None
    mock_rpc_channel.send_command.return_value = response

    await dock_info.refresh()

    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.GET_DOCK_INFO)
    assert dock_info.version == expected_version
    assert SERIAL not in repr(dock_info.as_dict())


@pytest.mark.parametrize("dock_type_code", [DOCK_INFO_DOCK])
@pytest.mark.parametrize(
    "response",
    [
        [],
        "unknown_method",
        0,
        SERIAL,
        [SERIAL],
        [[DOCK_INFO_DATA]],
        [DOCK_INFO_DATA, DOCK_INFO_DATA],
        {"sn": SERIAL, "version": {"sn": SERIAL}},
        {"sn": SERIAL, "version": [SERIAL]},
        {"sn": SERIAL, "version": 1.5},
        {"sn": SERIAL, "version": True},
    ],
)
async def test_refresh_parsing_error(
    dock_info: DockInfoTrait | None,
    mock_rpc_channel: AsyncMock,
    dock_type_code: RoborockDockTypeCode,
    response: Any,
) -> None:
    """Malformed responses raise a parsing error without the serial and keep the last read version."""
    assert dock_info is not None
    mock_rpc_channel.send_command.return_value = DOCK_INFO_DATA
    await dock_info.refresh()
    mock_rpc_channel.send_command.return_value = response

    with pytest.raises(RoborockParsingException, match="GET_DOCK_INFO") as exc_info:
        await dock_info.refresh()

    exc = exc_info.value
    assert exc.__cause__ is None
    assert exc.__context__ is None
    for text in (str(exc), repr(exc), repr(exc.args), repr(vars(exc))):
        assert SERIAL not in text
    assert dock_info.version == "0060"
