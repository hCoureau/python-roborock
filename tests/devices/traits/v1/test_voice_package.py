"""Tests for the VoicePackageTrait class."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from roborock.devices.device import RoborockDevice
from roborock.devices.traits.v1.voice_package import VoicePackageTrait
from roborock.exceptions import RoborockParsingException
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
def voice_package_trait(device: RoborockDevice) -> VoicePackageTrait:
    """Return the voice package trait from the device properties."""
    assert device.v1_properties
    return device.v1_properties.voice_package


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ([CURRENT_SOUND], CURRENT_SOUND),
        (CURRENT_SOUND, CURRENT_SOUND),
        ({"sid_in_use": 3, "language": "en"}, {"sid_in_use": 3, "language": "en"}),
    ],
    ids=["captured-list", "dict", "partial"],
)
async def test_refresh(
    voice_package_trait: VoicePackageTrait,
    mock_rpc_channel: AsyncMock,
    response: Any,
    expected: dict[str, Any],
) -> None:
    """Refresh populates the reported fields and leaves missing ones unset."""
    mock_rpc_channel.send_command.return_value = response

    await voice_package_trait.refresh()

    for field in CURRENT_SOUND:
        assert getattr(voice_package_trait, field) == expected.get(field)
    mock_rpc_channel.send_command.assert_awaited_once_with(RoborockCommand.GET_CURRENT_SOUND)


@pytest.mark.parametrize("response", [[], "invalid", 3], ids=["empty-list", "string", "integer"])
async def test_refresh_invalid_response(
    voice_package_trait: VoicePackageTrait, mock_rpc_channel: AsyncMock, response: Any
) -> None:
    """Unexpected payloads raise a parsing error naming the command and keep the last package."""
    mock_rpc_channel.send_command.return_value = [CURRENT_SOUND]
    await voice_package_trait.refresh()
    mock_rpc_channel.send_command.return_value = response

    with pytest.raises(RoborockParsingException, match="GET_CURRENT_SOUND"):
        await voice_package_trait.refresh()

    for field, value in CURRENT_SOUND.items():
        assert getattr(voice_package_trait, field) == value
