"""Tests for the optional dock metadata trait."""

from typing import Any
from unittest.mock import AsyncMock, call

import pytest

from roborock.data import DockInfo, HomeDataDevice, RoborockDockTypeCode
from roborock.devices.device import RoborockDevice
from roborock.exceptions import RoborockException, RoborockParsingException, RoborockUnsupportedFeature
from roborock.roborock_typing import RoborockCommand
from tests import mock_data


@pytest.fixture(name="dock_type_code", autouse=True)
def dock_type_code_fixture(request: pytest.FixtureRequest) -> RoborockDockTypeCode | None:
    """Default to the only dock family with an observed metadata response."""
    return getattr(request, "param", RoborockDockTypeCode.f1_dock)


@pytest.fixture(autouse=True)
async def discover_features_fixture(
    device: RoborockDevice,
    mock_rpc_channel: AsyncMock,
    dock_type_code: RoborockDockTypeCode | None,
    device_info: HomeDataDevice,
) -> None:
    """Discover on the shared device and verify the complete startup history."""
    assert device.v1_properties
    new_feature_info_str = device_info.new_feature_set
    assert new_feature_info_str is not None, f"Device {device_info.name} is missing new_feature_set"
    new_feature_info = int(new_feature_info_str, 16)
    mock_rpc_channel.send_command.side_effect = [
        [
            {
                **mock_data.APP_GET_INIT_STATUS,
                "new_feature_info_str": new_feature_info_str,
                "new_feature_info": new_feature_info,
            }
        ],
        {**mock_data.STATUS, "dock_type": dock_type_code},
    ]
    await device.connect()
    startup_calls = list(mock_rpc_channel.send_command.call_args_list)
    assert startup_calls == [call(RoborockCommand.APP_GET_INIT_STATUS), call(RoborockCommand.GET_STATUS)]
    assert device.v1_properties.status.dock_type == dock_type_code
    mock_rpc_channel.send_command.reset_mock()
    mock_rpc_channel.send_command.side_effect = None


async def test_discovery(device: RoborockDevice, mock_rpc_channel: AsyncMock) -> None:
    """Supported dock metadata is discoverable and empty until explicitly refreshed."""
    assert device.v1_properties
    assert isinstance(device.v1_properties.dock_info, DockInfo)
    assert device.v1_properties.dock_info.version is None
    mock_rpc_channel.send_command.assert_not_called()


@pytest.mark.parametrize(
    "dock_type_code",
    [
        None,
        RoborockDockTypeCode.o0_dock,
        RoborockDockTypeCode.o1_dock,
        RoborockDockTypeCode.pearl_dock,
        RoborockDockTypeCode.unknown,
    ],
    indirect=True,
)
async def test_other_dock_absent(device: RoborockDevice, mock_rpc_channel: AsyncMock) -> None:
    """No dock, basic, other and unknown docks do not expose this optional trait."""
    assert device.v1_properties
    assert device.v1_properties.dock_info is None
    mock_rpc_channel.send_command.assert_not_called()


@pytest.mark.parametrize(
    ("response", "expected_version"),
    [
        ({"sn": "synthetic-private-serial", "version": "0060"}, "0060"),
        ([{"sn": "synthetic-private-serial", "version": "0060"}], "0060"),
        ({"sn": "synthetic-private-serial"}, None),
        ({"sn": "synthetic-private-serial", "version": None}, None),
        ({"sn": "synthetic-private-serial", "version": "future-dock-version"}, "future-dock-version"),
        ({"sn": "synthetic-private-serial", "version": ""}, ""),
        ({"sn": "synthetic-private-serial", "version": "None"}, "None"),
    ],
)
async def test_refresh(
    device: RoborockDevice,
    mock_rpc_channel: AsyncMock,
    response: Any,
    expected_version: str | None,
) -> None:
    """Read only reported version metadata through the public dock trait."""
    assert device.v1_properties
    mock_rpc_channel.send_command.return_value = response

    info = device.v1_properties.dock_info
    assert info is not None
    await info.refresh()

    assert isinstance(info, DockInfo)
    assert info.version == expected_version
    assert info.as_dict() == ({"version": expected_version} if expected_version is not None else {})
    assert "synthetic-private-serial" not in repr(info)
    assert "sn" not in info.as_dict()
    assert "synthetic-private-serial" not in repr(device.v1_properties.as_dict())
    assert "synthetic-private-serial" not in repr(device.diagnostic_data())
    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.GET_DOCK_INFO)


@pytest.mark.parametrize(
    ("response", "expected_context", "error_type"),
    [
        ([], {"response": "[REDACTED]", "response_type": "list", "response_length": 0}, ValueError),
        (
            [{"sn": "synthetic-private-serial"}, {"version": "0060"}],
            {"response": "[REDACTED]", "response_type": "list", "response_length": 2},
            ValueError,
        ),
        (
            ["synthetic-private-serial"],
            {"response": "[REDACTED]", "response_type": "list", "response_length": 1},
            TypeError,
        ),
        ("synthetic-private-serial", {"response": "[REDACTED]", "response_type": "str"}, TypeError),
        (None, {"response": "[REDACTED]", "response_type": "NoneType"}, TypeError),
        (
            {"sn": "synthetic-private-serial", "version": 60},
            {"response": "[REDACTED]", "response_type": "dict", "version_type": "int"},
            TypeError,
        ),
        (
            {"sn": "synthetic-private-serial", "version": True},
            {"response": "[REDACTED]", "response_type": "dict", "version_type": "bool"},
            TypeError,
        ),
        (
            {"sn": "synthetic-private-serial", "version": {"sn": "synthetic-private-serial"}},
            {"response": "[REDACTED]", "response_type": "dict", "version_type": "dict"},
            TypeError,
        ),
        (
            [{"sn": "synthetic-private-serial", "version": ["synthetic-private-serial"]}],
            {"response": "[REDACTED]", "response_type": "list", "response_length": 1, "version_type": "list"},
            TypeError,
        ),
    ],
)
async def test_refresh_parsing_error(
    device: RoborockDevice,
    mock_rpc_channel: AsyncMock,
    response: Any,
    expected_context: dict[str, Any],
    error_type: type[Exception],
) -> None:
    """Malformed responses retain parsing context without leaking raw identifiers."""
    assert device.v1_properties
    info = device.v1_properties.dock_info
    assert info is not None
    mock_rpc_channel.send_command.return_value = {"version": "0060"}
    await info.refresh()
    mock_rpc_channel.send_command.reset_mock()
    mock_rpc_channel.send_command.return_value = response

    with pytest.raises(RoborockParsingException) as exc_info:
        await info.refresh()
    assert info.version == "0060"

    error = exc_info.value
    assert "DockInfoTrait" in str(error)
    assert "GET_DOCK_INFO" in str(error)
    assert repr(expected_context) in str(error)
    assert isinstance(error.__cause__, error_type)
    assert "synthetic-private-serial" not in str(error)
    assert "synthetic-private-serial" not in repr(error)
    assert "synthetic-private-serial" not in repr(error.__cause__)
    assert "sn" not in info.as_dict()
    assert "synthetic-private-serial" not in repr(device.v1_properties.as_dict())
    assert "synthetic-private-serial" not in repr(device.diagnostic_data())
    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.GET_DOCK_INFO)


@pytest.mark.parametrize(
    "error", [RoborockException("Communication error"), RoborockUnsupportedFeature("unknown_method")]
)
async def test_refresh_propagates_rpc_error(
    device: RoborockDevice, mock_rpc_channel: AsyncMock, error: RoborockException
) -> None:
    """RPC errors propagate unchanged without retrying or discarding cached metadata."""
    assert device.v1_properties
    info = device.v1_properties.dock_info
    assert info is not None
    mock_rpc_channel.send_command.return_value = {"version": "0060"}
    await info.refresh()
    mock_rpc_channel.send_command.reset_mock()
    mock_rpc_channel.send_command.side_effect = error

    with pytest.raises(RoborockException) as exc_info:
        await info.refresh()

    assert exc_info.value is error
    assert info.version == "0060"
    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.GET_DOCK_INFO)


@pytest.mark.parametrize("response", [{}, {"version": None}, [{"version": None}]])
async def test_refresh_clears_missing_version(
    device: RoborockDevice, mock_rpc_channel: AsyncMock, response: Any
) -> None:
    """A successful missing or null response replaces previously cached metadata."""
    assert device.v1_properties
    info = device.v1_properties.dock_info
    assert info is not None
    mock_rpc_channel.send_command.return_value = {"version": "0060"}
    await info.refresh()
    mock_rpc_channel.send_command.reset_mock()
    mock_rpc_channel.send_command.return_value = response

    await info.refresh()

    assert info.version is None
    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.GET_DOCK_INFO)
