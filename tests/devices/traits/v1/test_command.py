"""Tests for the CommandTrait class."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from roborock.data import DockInfo
from roborock.devices.device import RoborockDevice
from roborock.devices.traits.v1.command import CommandTrait
from roborock.exceptions import RoborockException, RoborockParsingException
from roborock.roborock_typing import RoborockCommand


@pytest.fixture(name="command_trait")
def command_trait_fixture() -> CommandTrait:
    """Create a CommandTrait instance with a mocked RPC channel."""
    trait = CommandTrait()
    trait._rpc_channel = AsyncMock()  # type: ignore[assignment]
    return trait


async def test_send_command_success(command_trait: CommandTrait) -> None:
    """Test successfully sending a command."""
    mock_rpc_channel = command_trait._rpc_channel
    assert mock_rpc_channel is not None
    mock_rpc_channel.send_command.return_value = {"result": "ok"}

    # Call the method
    result = await command_trait.send(RoborockCommand.APP_START)

    # Verify the result
    assert result == {"result": "ok"}

    # Verify the RPC call was made correctly
    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.APP_START, params=None)


async def test_send_command_with_params(command_trait: CommandTrait) -> None:
    """Test successfully sending a command with parameters."""
    mock_rpc_channel = command_trait._rpc_channel
    assert mock_rpc_channel is not None
    mock_rpc_channel.send_command.return_value = {"result": "ok"}
    params = {"segments": [1, 2, 3]}

    # Call the method
    result = await command_trait.send(RoborockCommand.APP_SEGMENT_CLEAN, params)

    # Verify the result
    assert result == {"result": "ok"}

    # Verify the RPC call was made correctly
    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.APP_SEGMENT_CLEAN, params=params)


async def test_send_command_propagates_exception(command_trait: CommandTrait) -> None:
    """Test that exceptions from RPC channel are propagated."""
    mock_rpc_channel = command_trait._rpc_channel
    assert mock_rpc_channel is not None
    mock_rpc_channel.send_command.side_effect = RoborockException("Communication error")

    # Verify the exception is propagated
    with pytest.raises(RoborockException, match="Communication error"):
        await command_trait.send(RoborockCommand.APP_START)


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
async def test_get_dock_info(
    device: RoborockDevice,
    mock_rpc_channel: AsyncMock,
    response: Any,
    expected_version: str | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Read only reported version metadata through the public command trait."""
    assert device.v1_properties
    mock_rpc_channel.send_command.return_value = response

    info = await device.v1_properties.command.get_dock_info()

    assert isinstance(info, DockInfo)
    assert info.version == expected_version
    assert info.as_dict() == ({"version": expected_version} if expected_version is not None else {})
    assert "synthetic-private-serial" not in repr(info)
    assert "synthetic-private-serial" not in repr(device.diagnostic_data())
    assert "synthetic-private-serial" not in caplog.text
    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.GET_DOCK_INFO, params=None)


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
async def test_get_dock_info_parsing_error(
    device: RoborockDevice,
    mock_rpc_channel: AsyncMock,
    response: Any,
    expected_context: dict[str, Any],
    error_type: type[Exception],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Malformed responses retain parsing context without leaking raw identifiers."""
    assert device.v1_properties
    mock_rpc_channel.send_command.return_value = response

    with pytest.raises(RoborockParsingException) as exc_info:
        await device.v1_properties.command.get_dock_info()

    error = exc_info.value
    assert "CommandTrait" in str(error)
    assert "GET_DOCK_INFO" in str(error)
    assert repr(expected_context) in str(error)
    assert isinstance(error.__cause__, error_type)
    assert "synthetic-private-serial" not in str(error)
    assert "synthetic-private-serial" not in repr(error)
    assert "synthetic-private-serial" not in repr(error.__cause__)
    assert "synthetic-private-serial" not in repr(device.diagnostic_data())
    assert "synthetic-private-serial" not in caplog.text
    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.GET_DOCK_INFO, params=None)


async def test_get_dock_info_propagates_rpc_error(device: RoborockDevice, mock_rpc_channel: AsyncMock) -> None:
    """An RPC failure propagates unchanged without retrying the read."""
    assert device.v1_properties
    error = RoborockException("Communication error")
    mock_rpc_channel.send_command.side_effect = error

    with pytest.raises(RoborockException) as exc_info:
        await device.v1_properties.command.get_dock_info()

    assert exc_info.value is error
    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.GET_DOCK_INFO, params=None)
