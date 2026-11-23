"""Tests for the TimezoneTrait class."""

import sys
import zoneinfo
from collections.abc import Iterator
from unittest.mock import AsyncMock

import pytest

from roborock.devices.device import RoborockDevice
from roborock.devices.traits.v1.timezone import TimezoneTrait
from roborock.exceptions import RoborockException, RoborockParsingException
from roborock.roborock_typing import RoborockCommand


@pytest.fixture(name="timezone")
def timezone_fixture(device: RoborockDevice) -> TimezoneTrait:
    """Get the timezone trait from the device."""
    assert device.v1_properties
    return device.v1_properties.timezone


@pytest.fixture(name="no_tz_database")
def no_tz_database_fixture(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Simulate a host with no system tz database and no `tzdata` package."""
    monkeypatch.setitem(sys.modules, "tzdata", None)
    zoneinfo.reset_tzpath(to=[])
    zoneinfo.ZoneInfo.clear_cache()
    yield
    zoneinfo.reset_tzpath()
    zoneinfo.ZoneInfo.clear_cache()


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (["Europe/Berlin"], "Europe/Berlin"),
        (["US/Pacific"], "US/Pacific"),
        (["UTC"], "UTC"),
    ],
)
async def test_refresh_timezone(
    timezone: TimezoneTrait, mock_rpc_channel: AsyncMock, response: list[str], expected: str
) -> None:
    """Test that refreshing reads the robot's timezone identifier."""
    assert timezone.identifier is None
    mock_rpc_channel.send_command.return_value = response

    await timezone.refresh()

    assert timezone.identifier == expected
    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.GET_TIMEZONE)


@pytest.mark.parametrize("response", [[], [""], [42], 42, "UTC", {"timezone": "Europe/Berlin"}])
async def test_refresh_invalid_response(
    timezone: TimezoneTrait, mock_rpc_channel: AsyncMock, response: list | int | dict
) -> None:
    """Test that unexpected responses raise a parsing error and keep the current value."""
    mock_rpc_channel.send_command.return_value = response

    with pytest.raises(RoborockParsingException):
        await timezone.refresh()

    assert timezone.identifier is None


@pytest.mark.parametrize("ack", [["ok"], {}])
@pytest.mark.parametrize(
    "identifier",
    ["Europe/Berlin", "US/Pacific", "UTC", "Etc/GMT+5", "America/Argentina/Buenos_Aires", "America/Port-au-Prince"],
)
async def test_set_timezone(
    timezone: TimezoneTrait, mock_rpc_channel: AsyncMock, identifier: str, ack: list[str] | dict
) -> None:
    """Test that setting the timezone sends the identifier and updates the trait on an ack."""
    mock_rpc_channel.send_command.return_value = ack

    await timezone.set_timezone(identifier)

    assert timezone.identifier == identifier
    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.SET_TIMEZONE, params=[identifier])


@pytest.mark.usefixtures("no_tz_database")
async def test_set_timezone_without_host_tz_database(timezone: TimezoneTrait, mock_rpc_channel: AsyncMock) -> None:
    """Test that validation does not depend on the host's tz database."""
    mock_rpc_channel.send_command.return_value = ["ok"]

    await timezone.set_timezone("Europe/Berlin")

    assert timezone.identifier == "Europe/Berlin"
    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.SET_TIMEZONE, params=["Europe/Berlin"])


@pytest.mark.parametrize(
    "identifier",
    ["", " Europe/Berlin", "Europe/Berlin ", "Europe/ Berlin", "../etc/passwd", "Europe/../Berlin", "/etc/localtime"],
)
async def test_set_invalid_timezone(timezone: TimezoneTrait, mock_rpc_channel: AsyncMock, identifier: str) -> None:
    """Test that malformed identifiers are rejected without sending a command."""
    with pytest.raises(ValueError, match="Invalid timezone identifier"):
        await timezone.set_timezone(identifier)

    assert timezone.identifier is None
    mock_rpc_channel.send_command.assert_not_called()


async def test_set_timezone_failure(timezone: TimezoneTrait, mock_rpc_channel: AsyncMock) -> None:
    """Test that a failed command keeps the last reported timezone."""
    mock_rpc_channel.send_command.return_value = ["UTC"]
    await timezone.refresh()
    mock_rpc_channel.send_command.side_effect = RoborockException("Command failed")

    with pytest.raises(RoborockException):
        await timezone.set_timezone("Europe/Berlin")

    assert timezone.identifier == "UTC"


@pytest.mark.parametrize("response", [["error"], "error", {"result": "error"}, [], 0])
async def test_set_timezone_not_acknowledged(
    timezone: TimezoneTrait, mock_rpc_channel: AsyncMock, response: list | str | dict | int
) -> None:
    """Test that a reply other than an ack raises and keeps the last reported timezone."""
    mock_rpc_channel.send_command.return_value = ["UTC"]
    await timezone.refresh()
    mock_rpc_channel.send_command.return_value = response

    with pytest.raises(RoborockException, match="set_timezone was not accepted"):
        await timezone.set_timezone("Europe/Berlin")

    assert timezone.identifier == "UTC"
