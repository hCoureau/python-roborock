"""Tests for the CommandTrait class."""

from unittest.mock import AsyncMock

import pytest

from roborock.devices.traits.v1.command import CommandTrait
from roborock.exceptions import RoborockException, RoborockParsingException, RoborockTimeout
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


@pytest.mark.parametrize("timezone", ["Europe/Berlin", "UTC", " America/Los_Angeles "])
async def test_get_robot_timezone(command_trait: CommandTrait, timezone: str) -> None:
    """Return the robot's singleton string response verbatim."""
    channel = command_trait._rpc_channel
    assert channel is not None
    channel.send_command.return_value = [timezone]

    assert await command_trait.get_robot_timezone() == timezone

    channel.send_command.assert_awaited_once_with(RoborockCommand.GET_TIMEZONE, params=None)


@pytest.mark.parametrize(
    "response",
    [
        "Europe/Berlin",
        [""],
        [" \t\n"],
        [],
        ["Europe/Berlin", "UTC"],
        42,
        [42],
        {"olson": "Europe/Berlin", "posix": "CET-1CEST,M3.5.0,M10.5.0/3"},
    ],
)
async def test_get_robot_timezone_invalid_response(command_trait: CommandTrait, response: object) -> None:
    """Reject malformed channel replies, including scalar strings returned by a fake channel.

    The real V1 decoder already treats non-ok scalar strings as API errors.
    """
    channel = command_trait._rpc_channel
    assert channel is not None
    channel.send_command.return_value = response

    with pytest.raises(RoborockParsingException) as exc_info:
        await command_trait.get_robot_timezone()

    assert "CommandTrait" in str(exc_info.value)
    assert "GET_TIMEZONE" in str(exc_info.value)
    assert repr(response) in str(exc_info.value)
    assert "singleton list" in str(exc_info.value)
    channel.send_command.assert_awaited_once_with(RoborockCommand.GET_TIMEZONE, params=None)


@pytest.mark.parametrize("timezone", ["Europe/Berlin", "UTC", " America/Los_Angeles "])
async def test_set_robot_timezone(command_trait: CommandTrait, timezone: str) -> None:
    """Send exactly one trait RPC with the supplied identifier and discard its acknowledgment."""
    channel = command_trait._rpc_channel
    assert channel is not None
    channel.send_command.return_value = ["ok"]

    assert await command_trait.set_robot_timezone(timezone) is None

    # No getter, locale, app-timezone or DND request is made by the trait.
    channel.send_command.assert_awaited_once_with(RoborockCommand.SET_TIMEZONE, params=[timezone])


@pytest.mark.parametrize("timezone", ["", " ", "\t\n"])
async def test_set_robot_timezone_empty_identifier(command_trait: CommandTrait, timezone: str) -> None:
    """Reject blank identifiers before sending any RPC."""
    channel = command_trait._rpc_channel
    assert channel is not None

    with pytest.raises(ValueError, match="Timezone identifier"):
        await command_trait.set_robot_timezone(timezone)

    channel.send_command.assert_not_called()


@pytest.mark.parametrize("operation", ["get", "set"])
@pytest.mark.parametrize("error", [RoborockException("Communication error"), RoborockTimeout("Timed out")])
async def test_robot_timezone_propagates_exception(
    command_trait: CommandTrait, operation: str, error: RoborockException
) -> None:
    """Propagate channel failures without adding a trait retry or readback."""
    channel = command_trait._rpc_channel
    assert channel is not None
    channel.send_command.side_effect = error

    with pytest.raises(type(error)) as exc_info:
        if operation == "get":
            await command_trait.get_robot_timezone()
        else:
            await command_trait.set_robot_timezone("Europe/Berlin")

    assert exc_info.value is error
    command = RoborockCommand.GET_TIMEZONE if operation == "get" else RoborockCommand.SET_TIMEZONE
    params = None if operation == "get" else ["Europe/Berlin"]
    channel.send_command.assert_awaited_once_with(command, params=params)
