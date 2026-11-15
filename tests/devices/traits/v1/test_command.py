"""Tests for the CommandTrait class."""

from unittest.mock import AsyncMock

import pytest

from roborock.data.v1 import RoborockZone
from roborock.devices.device import RoborockDevice
from roborock.devices.traits.v1.command import CommandTrait
from roborock.exceptions import RoborockException
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
    ("zones", "kwargs", "expected_params"),
    [
        ([RoborockZone(22000, 24000, 26000, 28000)], {}, [[22000, 24000, 26000, 28000, 1]]),
        (
            [RoborockZone(22000, 24000, 26000, 28000), RoborockZone(27000, 24000, 29000, 26000)],
            {"repeat": 2},
            [[22000, 24000, 26000, 28000, 2], [27000, 24000, 29000, 26000, 2]],
        ),
    ],
)
async def test_clean_zones(
    device: RoborockDevice,
    mock_rpc_channel: AsyncMock,
    zones: list[RoborockZone],
    kwargs: dict[str, int],
    expected_params: list[list[int]],
) -> None:
    """Test starting a zone clean."""
    assert device.v1_properties

    await device.v1_properties.command.clean_zones(zones, **kwargs)

    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.APP_ZONED_CLEAN, params=expected_params)


@pytest.mark.parametrize(
    "zone",
    [RoborockZone(22000, 24000, 22000, 28000), RoborockZone(22000, 24000, 26000, 24000)],
)
async def test_clean_zones_rejects_zero_area(
    device: RoborockDevice,
    mock_rpc_channel: AsyncMock,
    zone: RoborockZone,
) -> None:
    """Test that a zone without an area is rejected before sending."""
    assert device.v1_properties

    with pytest.raises(ValueError, match="Zone must enclose an area"):
        await device.v1_properties.command.clean_zones([zone])

    mock_rpc_channel.send_command.assert_not_called()
