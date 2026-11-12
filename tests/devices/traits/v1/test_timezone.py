"""Tests for explicit robot timezone state and commands."""

from unittest.mock import AsyncMock, call

import pytest

from roborock.devices.device import RoborockDevice
from roborock.devices.traits.v1.timezone import TimezoneTrait
from roborock.exceptions import RoborockException, RoborockParsingException, RoborockTimeout
from roborock.roborock_typing import RoborockCommand


@pytest.fixture(name="timezone")
async def timezone_fixture(
    device: RoborockDevice,
    mock_rpc_channel: AsyncMock,
    discover_features_fixture: None,
    reported_identifier: str | None,
) -> TimezoneTrait:
    """Obtain state through the public device API, optionally after a report."""
    assert device.v1_properties
    trait = device.v1_properties.timezone
    if reported_identifier is not None:
        mock_rpc_channel.send_command.return_value = [reported_identifier]
        await trait.refresh()
        mock_rpc_channel.send_command.reset_mock()
    return trait


@pytest.fixture(name="reported_identifier")
def reported_identifier_fixture(request: pytest.FixtureRequest) -> str | None:
    """Start unset unless the test requests an established device report."""
    return getattr(request, "param", None)


async def test_initial_timezone(timezone: TimezoneTrait) -> None:
    """No identifier is synthesized from the app-init data used in discovery."""
    assert timezone.identifier is None
    assert timezone.as_dict() == {}


@pytest.mark.parametrize("identifier", ["Europe/Berlin", "UTC", " America/Los_Angeles "])
async def test_refresh_timezone(timezone: TimezoneTrait, mock_rpc_channel: AsyncMock, identifier: str) -> None:
    """Refresh exposes the reported identifier verbatim."""
    mock_rpc_channel.send_command.return_value = [identifier]

    await timezone.refresh()

    assert timezone.identifier == identifier
    assert timezone.as_dict() == {"identifier": identifier}
    mock_rpc_channel.send_command.assert_awaited_once_with(RoborockCommand.GET_TIMEZONE)


@pytest.mark.parametrize("reported_identifier", [None, "UTC"], indirect=True)
@pytest.mark.parametrize(
    "response",
    [
        "Europe/Berlin",
        [],
        ["UTC", "Europe/Berlin"],
        [""],
        [" \t\n"],
        42,
        [42],
        b"UTC",
        [b"UTC"],
        {"olson": "Europe/Berlin", "posix": "CET-1CEST"},
        [{"olson": "Europe/Berlin"}],
    ],
)
async def test_refresh_invalid_response(
    timezone: TimezoneTrait,
    mock_rpc_channel: AsyncMock,
    reported_identifier: str | None,
    response: object,
) -> None:
    """Parsing failures retain state and include the dynamic wire context."""
    mock_rpc_channel.send_command.return_value = response

    with pytest.raises(RoborockParsingException) as exc_info:
        await timezone.refresh()

    assert timezone.identifier == reported_identifier
    assert "TimezoneTrait" in str(exc_info.value)
    assert "GET_TIMEZONE" in str(exc_info.value)
    assert repr(response) in str(exc_info.value)
    assert "singleton list" in str(exc_info.value)
    mock_rpc_channel.send_command.assert_awaited_once_with(RoborockCommand.GET_TIMEZONE)


@pytest.mark.parametrize("reported_identifier", [None, "UTC"], indirect=True)
@pytest.mark.parametrize("operation", ["refresh", "set"])
@pytest.mark.parametrize("error", [RoborockException("RPC failed"), RoborockTimeout("Timed out")])
async def test_timezone_rpc_failure(
    timezone: TimezoneTrait,
    mock_rpc_channel: AsyncMock,
    reported_identifier: str | None,
    operation: str,
    error: RoborockException,
) -> None:
    """Failures propagate without retries; existing state remains a last report."""
    mock_rpc_channel.send_command.side_effect = error

    with pytest.raises(type(error)) as exc_info:
        if operation == "refresh":
            await timezone.refresh()
        else:
            await timezone.set_timezone("Europe/Berlin")

    assert exc_info.value is error
    assert timezone.identifier == reported_identifier
    expected = (
        call(RoborockCommand.GET_TIMEZONE)
        if operation == "refresh"
        else call(RoborockCommand.SET_TIMEZONE, params=["Europe/Berlin"])
    )
    assert mock_rpc_channel.send_command.await_args_list == [expected]


@pytest.mark.parametrize("reported_identifier", [None, "UTC"], indirect=True)
@pytest.mark.parametrize("identifier", ["Europe/Berlin", "UTC", " America/Los_Angeles "])
async def test_set_timezone(timezone: TimezoneTrait, mock_rpc_channel: AsyncMock, identifier: str) -> None:
    """An accepted SET clears the report without requesting an automatic GET."""
    mock_rpc_channel.send_command.return_value = ["ok"]

    await timezone.set_timezone(identifier)

    assert timezone.identifier is None
    assert timezone.as_dict() == {}
    mock_rpc_channel.send_command.assert_awaited_once_with(RoborockCommand.SET_TIMEZONE, params=[identifier])


@pytest.mark.parametrize("reported_identifier", [None, "UTC"], indirect=True)
@pytest.mark.parametrize("identifier", ["", " ", "\t\n"])
async def test_set_blank_timezone(
    timezone: TimezoneTrait,
    mock_rpc_channel: AsyncMock,
    reported_identifier: str | None,
    identifier: str,
) -> None:
    """Invalid identifiers produce no RPC and preserve the last report."""
    with pytest.raises(ValueError, match="Timezone identifier"):
        await timezone.set_timezone(identifier)

    assert timezone.identifier == reported_identifier
    mock_rpc_channel.send_command.assert_not_called()


async def test_explicit_timezone_readback(
    timezone: TimezoneTrait, device: RoborockDevice, mock_rpc_channel: AsyncMock
) -> None:
    """Only successful reports populate diagnostics; accepted writes invalidate them."""
    assert device.v1_properties
    assert "timezone" not in device.v1_properties.as_dict()
    mock_rpc_channel.send_command.side_effect = [["UTC"], ["ok"], ["Europe/Berlin"]]

    await timezone.refresh()
    assert timezone.identifier == "UTC"
    assert device.v1_properties.as_dict()["timezone"] == {"identifier": "UTC"}

    await timezone.set_timezone("Europe/Berlin")
    assert timezone.identifier is None
    assert "timezone" not in device.v1_properties.as_dict()

    await timezone.refresh()
    assert timezone.identifier == "Europe/Berlin"
    assert device.v1_properties.as_dict()["timezone"] == {"identifier": "Europe/Berlin"}
    assert mock_rpc_channel.send_command.await_args_list == [
        call(RoborockCommand.GET_TIMEZONE),
        call(RoborockCommand.SET_TIMEZONE, params=["Europe/Berlin"]),
        call(RoborockCommand.GET_TIMEZONE),
    ]


async def test_failed_optional_readback(timezone: TimezoneTrait, mock_rpc_channel: AsyncMock) -> None:
    """A separate failed readback cannot turn an acknowledgment into reported state."""
    error = RoborockTimeout("Readback timed out")
    mock_rpc_channel.send_command.side_effect = [["UTC"], ["ok"], error]
    await timezone.refresh()
    await timezone.set_timezone("Europe/Berlin")

    with pytest.raises(RoborockTimeout) as exc_info:
        await timezone.refresh()

    assert exc_info.value is error
    assert timezone.identifier is None
    assert mock_rpc_channel.send_command.await_args_list == [
        call(RoborockCommand.GET_TIMEZONE),
        call(RoborockCommand.SET_TIMEZONE, params=["Europe/Berlin"]),
        call(RoborockCommand.GET_TIMEZONE),
    ]
