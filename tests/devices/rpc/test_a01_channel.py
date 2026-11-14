"""Tests for the a01_channel."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from roborock.devices.rpc.a01_channel import send_decoded_command
from roborock.exceptions import RoborockException
from roborock.protocols.a01_protocol import encode_mqtt_payload
from roborock.roborock_message import (
    RoborockDyadDataProtocol,
    RoborockMessage,
    RoborockMessageProtocol,
    RoborockZeoProtocol,
)
from tests.fixtures.channel_fixtures import FakeChannel


@pytest.fixture
def mock_mqtt_channel() -> FakeChannel:
    """Fixture for a fake MQTT channel."""
    return FakeChannel()


async def test_id_query(mock_mqtt_channel: FakeChannel):
    """Test successful command sending and response decoding."""
    # Command parameters to send
    params: dict[RoborockDyadDataProtocol, Any] = {
        RoborockDyadDataProtocol.ID_QUERY: [
            RoborockDyadDataProtocol.WARM_LEVEL,
            RoborockDyadDataProtocol.POWER,
        ]
    }
    encoded = encode_mqtt_payload(
        {
            RoborockDyadDataProtocol.WARM_LEVEL: 101,
            RoborockDyadDataProtocol.POWER: 75,
        },
        value_encoder=lambda x: x,
    )
    response_message = RoborockMessage(
        protocol=RoborockMessageProtocol.RPC_RESPONSE, payload=encoded.payload, version=encoded.version
    )
    mock_mqtt_channel.response_queue.append(response_message)

    # Call the function to be tested
    result = await send_decoded_command(mock_mqtt_channel, params)  # type: ignore[call-overload]

    # Assertions
    assert result == {
        RoborockDyadDataProtocol.WARM_LEVEL: 101,
        RoborockDyadDataProtocol.POWER: 75,
    }
    mock_mqtt_channel.publish.assert_awaited_once()
    mock_mqtt_channel.subscribe.assert_awaited_once()


async def test_query_marks_session_healthy(mock_mqtt_channel: FakeChannel):
    """A completed query reports success to the health manager."""
    mock_mqtt_channel.health_manager.on_success = AsyncMock()  # type: ignore[method-assign]
    mock_mqtt_channel.health_manager.on_timeout = AsyncMock()  # type: ignore[method-assign]

    params: dict[RoborockDyadDataProtocol, Any] = {RoborockDyadDataProtocol.ID_QUERY: [RoborockDyadDataProtocol.POWER]}
    encoded = encode_mqtt_payload({RoborockDyadDataProtocol.POWER: 75}, value_encoder=lambda x: x)
    mock_mqtt_channel.response_queue.append(
        RoborockMessage(protocol=RoborockMessageProtocol.RPC_RESPONSE, payload=encoded.payload, version=encoded.version)
    )

    await send_decoded_command(mock_mqtt_channel, params)  # type: ignore[call-overload]

    mock_mqtt_channel.health_manager.on_success.assert_awaited_once()
    mock_mqtt_channel.health_manager.on_timeout.assert_not_awaited()


async def test_query_timeout_reports_to_health_manager(mock_mqtt_channel: FakeChannel, monkeypatch):
    """A timed-out query reports to the health manager so a stale session can be restarted."""
    monkeypatch.setattr("roborock.devices.rpc.a01_channel._TIMEOUT", 0.01)
    mock_mqtt_channel.health_manager.on_timeout = AsyncMock()  # type: ignore[method-assign]
    mock_mqtt_channel.health_manager.on_success = AsyncMock()  # type: ignore[method-assign]

    params: dict[RoborockDyadDataProtocol, Any] = {RoborockDyadDataProtocol.ID_QUERY: [RoborockDyadDataProtocol.POWER]}

    with pytest.raises(RoborockException, match="timed out"):
        await send_decoded_command(mock_mqtt_channel, params)  # type: ignore[call-overload]

    mock_mqtt_channel.health_manager.on_timeout.assert_awaited_once()
    mock_mqtt_channel.health_manager.on_success.assert_not_awaited()


async def test_query_returns_partial_response_after_timeout(mock_mqtt_channel: FakeChannel, monkeypatch):
    """A device that omits a requested data point still yields the ones it sent."""
    monkeypatch.setattr("roborock.devices.rpc.a01_channel._TIMEOUT", 0.01)
    mock_mqtt_channel.health_manager.on_success = AsyncMock()  # type: ignore[method-assign]
    mock_mqtt_channel.health_manager.on_timeout = AsyncMock()  # type: ignore[method-assign]

    params: dict[RoborockZeoProtocol, Any] = {
        RoborockZeoProtocol.ID_QUERY: [
            RoborockZeoProtocol.STATE,
            RoborockZeoProtocol.WASHING_LEFT,
            RoborockZeoProtocol.SOFTENER_TYPE,
            RoborockZeoProtocol.SOFTENER_EMPTY,
        ]
    }
    encoded = encode_mqtt_payload(
        {RoborockZeoProtocol.STATE: 1, RoborockZeoProtocol.WASHING_LEFT: 42}, value_encoder=lambda x: x
    )
    mock_mqtt_channel.response_queue.append(
        RoborockMessage(protocol=RoborockMessageProtocol.RPC_RESPONSE, payload=encoded.payload, version=encoded.version)
    )

    result = await send_decoded_command(mock_mqtt_channel, params)  # type: ignore[call-overload]

    assert result == {RoborockZeoProtocol.STATE: 1, RoborockZeoProtocol.WASHING_LEFT: 42}
    mock_mqtt_channel.health_manager.on_success.assert_awaited_once()
    mock_mqtt_channel.health_manager.on_timeout.assert_not_awaited()


async def test_query_with_only_unrequested_data_points_times_out(mock_mqtt_channel: FakeChannel, monkeypatch):
    """A message carrying none of the requested data points does not count as a response."""
    monkeypatch.setattr("roborock.devices.rpc.a01_channel._TIMEOUT", 0.01)
    mock_mqtt_channel.health_manager.on_success = AsyncMock()  # type: ignore[method-assign]
    mock_mqtt_channel.health_manager.on_timeout = AsyncMock()  # type: ignore[method-assign]

    params: dict[RoborockDyadDataProtocol, Any] = {
        RoborockDyadDataProtocol.ID_QUERY: [RoborockDyadDataProtocol.WARM_LEVEL]
    }
    encoded = encode_mqtt_payload({RoborockDyadDataProtocol.POWER: 75}, value_encoder=lambda x: x)
    mock_mqtt_channel.response_queue.append(
        RoborockMessage(protocol=RoborockMessageProtocol.RPC_RESPONSE, payload=encoded.payload, version=encoded.version)
    )

    with pytest.raises(RoborockException, match="timed out"):
        await send_decoded_command(mock_mqtt_channel, params)  # type: ignore[call-overload]

    mock_mqtt_channel.health_manager.on_timeout.assert_awaited_once()
    mock_mqtt_channel.health_manager.on_success.assert_not_awaited()
