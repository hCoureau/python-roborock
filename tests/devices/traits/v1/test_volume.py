"""Tests for sound volume and read-only voice-package metadata."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from roborock.devices.device import RoborockDevice
from roborock.devices.traits.v1.volume import CurrentSound, SoundVolumeTrait
from roborock.exceptions import RoborockParsingException, RoborockTimeout
from roborock.roborock_typing import RoborockCommand

# Captured get_current_sound response from a Qrevo device.
CURRENT_SOUND = {
    "sid_in_use": 3,
    "sid_version": 4,
    "sid_in_progress": 0,
    "location": "de",
    "bom": "A.03.0925",
    "language": "en",
    "msg_ver": 2,
}


@pytest.fixture
def volume_trait(device: RoborockDevice) -> SoundVolumeTrait:
    """Access the sound volume trait through the public device properties."""
    assert device.v1_properties
    return device.v1_properties.sound_volume


@pytest.mark.parametrize("response", [[CURRENT_SOUND], CURRENT_SOUND], ids=["captured-list", "dict"])
async def test_get_current_sound(volume_trait: SoundVolumeTrait, mock_rpc_channel: AsyncMock, response: Any) -> None:
    """Read all captured fields without changing sound volume."""
    volume_trait.volume = 37
    mock_rpc_channel.send_command.return_value = response

    sound = await volume_trait.get_current_sound()

    assert sound == CurrentSound(
        sid_in_use=3,
        sid_version=4,
        sid_in_progress=0,
        msg_ver=2,
        location="de",
        bom="A.03.0925",
        language="en",
    )
    assert volume_trait.volume == 37
    mock_rpc_channel.send_command.assert_awaited_once_with(RoborockCommand.GET_CURRENT_SOUND)


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ({}, CurrentSound()),
        ({"language": "en"}, CurrentSound(language="en")),
        (
            {"sid_in_use": 0, "sid_version": 0, "sid_in_progress": 0, "msg_ver": 0},
            CurrentSound(sid_in_use=0, sid_version=0, sid_in_progress=0, msg_ver=0),
        ),
        (
            {"sid_in_use": 9999, "sid_version": 4321, "sid_in_progress": -1, "msg_ver": 1234, "future_field": 7},
            CurrentSound(sid_in_use=9999, sid_version=4321, sid_in_progress=-1, msg_ver=1234),
        ),
    ],
    ids=["missing", "partial", "zero", "unknown-values"],
)
async def test_get_current_sound_optional_fields(
    volume_trait: SoundVolumeTrait, mock_rpc_channel: AsyncMock, response: dict, expected: CurrentSound
) -> None:
    """Preserve reported integer values and leave absent fields unset."""
    mock_rpc_channel.send_command.return_value = response

    assert await volume_trait.get_current_sound() == expected
    assert volume_trait.volume is None
    mock_rpc_channel.send_command.assert_awaited_once_with(RoborockCommand.GET_CURRENT_SOUND)


@pytest.mark.parametrize("field", ["sid_in_use", "sid_version", "sid_in_progress", "msg_ver"])
async def test_get_current_sound_malformed_integer(
    volume_trait: SoundVolumeTrait, mock_rpc_channel: AsyncMock, field: str
) -> None:
    """Use the shared parser's omission behavior for unconvertible optional integers."""
    mock_rpc_channel.send_command.return_value = {field: "invalid", "language": "en"}

    assert await volume_trait.get_current_sound() == CurrentSound(language="en")
    assert volume_trait.volume is None
    mock_rpc_channel.send_command.assert_awaited_once_with(RoborockCommand.GET_CURRENT_SOUND)


@pytest.mark.parametrize(
    "response",
    [[], [{}, {}], 3, "invalid", None, [3], [[]], {1: 3}],
    ids=["empty", "multiple", "integer", "string", "null", "list-scalar", "nested-list", "invalid-key"],
)
async def test_get_current_sound_invalid_response(
    volume_trait: SoundVolumeTrait, mock_rpc_channel: AsyncMock, response: Any
) -> None:
    """Include the original response and command in parsing failures."""
    volume_trait.volume = 37
    mock_rpc_channel.send_command.return_value = response

    with pytest.raises(RoborockParsingException) as exc_info:
        await volume_trait.get_current_sound()

    message = str(exc_info.value)
    assert "SoundVolumeTrait" in message
    assert "GET_CURRENT_SOUND" in message
    assert f"Payload: {response!r}" in message
    assert isinstance(exc_info.value.__cause__, (TypeError, ValueError))
    assert repr(exc_info.value.__cause__) in message
    assert volume_trait.volume == 37
    mock_rpc_channel.send_command.assert_awaited_once_with(RoborockCommand.GET_CURRENT_SOUND)


async def test_get_current_sound_transport_failure(volume_trait: SoundVolumeTrait, mock_rpc_channel: AsyncMock) -> None:
    """Propagate transport failures without changing volume."""
    volume_trait.volume = 37
    error = RoborockTimeout("Communication error")
    mock_rpc_channel.send_command.side_effect = error

    with pytest.raises(RoborockTimeout) as exc_info:
        await volume_trait.get_current_sound()

    assert exc_info.value is error
    assert volume_trait.volume == 37
    mock_rpc_channel.send_command.assert_awaited_once_with(RoborockCommand.GET_CURRENT_SOUND)


async def test_set_volume(volume_trait: SoundVolumeTrait, mock_rpc_channel: AsyncMock) -> None:
    """Update the volume optimistically after the command succeeds."""
    volume_trait.volume = 37

    await volume_trait.set_volume(60)

    assert volume_trait.volume == 60
    mock_rpc_channel.send_command.assert_awaited_once_with(RoborockCommand.CHANGE_SOUND_VOLUME, params=[60])


async def test_set_volume_transport_failure(volume_trait: SoundVolumeTrait, mock_rpc_channel: AsyncMock) -> None:
    """Keep the previous volume when setting it fails."""
    volume_trait.volume = 37
    error = RoborockTimeout("Communication error")
    mock_rpc_channel.send_command.side_effect = error

    with pytest.raises(RoborockTimeout) as exc_info:
        await volume_trait.set_volume(60)

    assert exc_info.value is error
    assert volume_trait.volume == 37
    mock_rpc_channel.send_command.assert_awaited_once_with(RoborockCommand.CHANGE_SOUND_VOLUME, params=[60])


async def test_refresh_volume(volume_trait: SoundVolumeTrait, mock_rpc_channel: AsyncMock) -> None:
    """Refresh continues to read sound volume independently of package metadata."""
    mock_rpc_channel.send_command.return_value = [60]

    await volume_trait.refresh()

    assert volume_trait.volume == 60
    mock_rpc_channel.send_command.assert_awaited_once_with(RoborockCommand.GET_SOUND_VOLUME)


async def test_refresh_volume_transport_failure(volume_trait: SoundVolumeTrait, mock_rpc_channel: AsyncMock) -> None:
    """Keep the previous volume when refreshing it fails."""
    volume_trait.volume = 37
    error = RoborockTimeout("Communication error")
    mock_rpc_channel.send_command.side_effect = error

    with pytest.raises(RoborockTimeout) as exc_info:
        await volume_trait.refresh()

    assert exc_info.value is error
    assert volume_trait.volume == 37
    mock_rpc_channel.send_command.assert_awaited_once_with(RoborockCommand.GET_SOUND_VOLUME)
