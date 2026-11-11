"""Tests for the CommandTrait class."""

from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from roborock.data.v1 import RoborockZone
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


@pytest.mark.parametrize("zone_count", [1, 5])
@pytest.mark.parametrize("total_passes", [1, 2, 3])
async def test_clean_zones(command_trait: CommandTrait, zone_count: int, total_passes: int) -> None:
    """Send native coordinates in caller order without changing the supplied zones."""
    mock_rpc_channel = command_trait._rpc_channel
    assert mock_rpc_channel is not None
    mock_rpc_channel.send_command.return_value = {"result": "ok"}
    zones = [RoborockZone(22000 + i * 1000, 24000, 22500 + i * 1000, 28000) for i in range(zone_count)]
    original_zones = deepcopy(zones)

    result = await command_trait.clean_zones(zones, total_passes=total_passes)

    assert result is None
    assert zones == original_zones
    mock_rpc_channel.send_command.assert_awaited_once_with(
        RoborockCommand.APP_ZONED_CLEAN,
        params=[[22000 + i * 1000, 24000, 22500 + i * 1000, 28000, total_passes] for i in range(zone_count)],
    )


async def test_clean_zones_default_passes(command_trait: CommandTrait) -> None:
    """Use one total pass and preserve coordinates without imposing an arbitrary envelope."""
    mock_rpc_channel = command_trait._rpc_channel
    assert mock_rpc_channel is not None

    await command_trait.clean_zones([RoborockZone(-100, 0, 100, 100000)])

    mock_rpc_channel.send_command.assert_awaited_once_with(
        RoborockCommand.APP_ZONED_CLEAN, params=[[-100, 0, 100, 100000, 1]]
    )


@pytest.mark.parametrize(
    ("zones", "total_passes"),
    [
        ([], 1),
        ([RoborockZone(22000, 24000, 26000, 28000)] * 6, 1),
        ([RoborockZone(22000, 24000, 26000, 28000)], 0),
        ([RoborockZone(22000, 24000, 26000, 28000)], 4),
        ([RoborockZone(26000, 24000, 22000, 28000)], 1),
        ([RoborockZone(22000, 28000, 26000, 24000)], 1),
        ([RoborockZone(22000, 24000, 22000, 28000)], 1),
        ([RoborockZone(22000, 24000, 26000, 24000)], 1),
        ([RoborockZone(22000, 24000, 26000, 28000), RoborockZone(26000, 24000, 22000, 28000)], 1),
    ],
)
async def test_clean_zones_invalid_request(
    command_trait: CommandTrait, zones: list[RoborockZone], total_passes: int
) -> None:
    """Reject invalid requests before sending any command."""
    mock_rpc_channel = command_trait._rpc_channel
    assert mock_rpc_channel is not None

    with pytest.raises(ValueError):
        await command_trait.clean_zones(zones, total_passes=total_passes)

    mock_rpc_channel.send_command.assert_not_awaited()


async def test_clean_zones_propagates_exception(command_trait: CommandTrait) -> None:
    """Propagate channel failures without issuing a follow-up command."""
    mock_rpc_channel = command_trait._rpc_channel
    assert mock_rpc_channel is not None
    mock_rpc_channel.send_command.side_effect = RoborockException("Communication error")

    with pytest.raises(RoborockException, match="Communication error"):
        await command_trait.clean_zones([RoborockZone(22000, 24000, 26000, 28000)])

    mock_rpc_channel.send_command.assert_awaited_once_with(
        RoborockCommand.APP_ZONED_CLEAN, params=[[22000, 24000, 26000, 28000, 1]]
    )
