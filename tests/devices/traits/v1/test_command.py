"""Tests for the CommandTrait class."""

from unittest.mock import AsyncMock

import pytest

from roborock.devices.device import RoborockDevice
from roborock.devices.traits.v1.command import CommandTrait
from roborock.exceptions import RoborockException, RoborockTimeout
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


@pytest.mark.parametrize("segments", [[17], [17, 19]])
@pytest.mark.parametrize("repeat", [None, 2])
async def test_clean_rooms(
    device: RoborockDevice,
    mock_rpc_channel: AsyncMock,
    segments: list[int],
    repeat: int | None,
) -> None:
    """Start room cleaning through the device API with the exact request."""
    assert device.v1_properties
    command = device.v1_properties.command

    if repeat is None:
        await command.clean_rooms(segments)
    else:
        await command.clean_rooms(segments, repeat=repeat)

    mock_rpc_channel.send_command.assert_awaited_once_with(
        RoborockCommand.APP_SEGMENT_CLEAN,
        params=[{"segments": segments, "repeat": 1 if repeat is None else repeat}],
    )


@pytest.mark.parametrize(
    ("segments", "repeat"),
    [
        ([], 1),
        ([0], 1),
        ([-1], 1),
        ([17, 0], 1),
        ([17, -1], 1),
        ([17], 0),
        ([17], -1),
    ],
)
async def test_clean_rooms_invalid_request(
    device: RoborockDevice,
    mock_rpc_channel: AsyncMock,
    segments: list[int],
    repeat: int,
) -> None:
    """Reject invalid room requests before sending commands."""
    assert device.v1_properties

    with pytest.raises(ValueError):
        await device.v1_properties.command.clean_rooms(segments, repeat=repeat)

    mock_rpc_channel.send_command.assert_not_called()


async def test_clean_rooms_copies_segments(device: RoborockDevice, mock_rpc_channel: AsyncMock) -> None:
    """Keep the sent request independent of later changes to the input list."""
    assert device.v1_properties
    segments = [17, 19]

    await device.v1_properties.command.clean_rooms(segments, repeat=2)
    segments.append(21)

    mock_rpc_channel.send_command.assert_awaited_once_with(
        RoborockCommand.APP_SEGMENT_CLEAN,
        params=[{"segments": [17, 19], "repeat": 2}],
    )


@pytest.mark.parametrize("error", [RoborockException("Communication error"), RoborockTimeout("Communication error")])
async def test_clean_rooms_propagates_exception(
    device: RoborockDevice,
    mock_rpc_channel: AsyncMock,
    error: RoborockException,
) -> None:
    """Propagate channel failures without adding a retry."""
    assert device.v1_properties
    mock_rpc_channel.send_command.side_effect = error

    with pytest.raises(type(error), match="Communication error"):
        await device.v1_properties.command.clean_rooms([17, 19], repeat=2)

    mock_rpc_channel.send_command.assert_awaited_once_with(
        RoborockCommand.APP_SEGMENT_CLEAN,
        params=[{"segments": [17, 19], "repeat": 2}],
    )
