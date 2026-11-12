"""Tests for the SmartWashParamsTrait class."""

from unittest.mock import AsyncMock, call

import pytest

from roborock.data.v1.v1_code_mappings import (
    RoborockDockTypeCode,
    RoborockSmartWashMode,
)
from roborock.devices.device import RoborockDevice
from roborock.devices.traits.v1.smart_wash_params import SmartWashParamsTrait
from roborock.exceptions import RoborockTimeout
from roborock.roborock_typing import RoborockCommand
from tests.devices.traits.v1.helpers import dock_types_with_capability

SMART_WASH_DATA = [{"smart_wash": 5, "wash_interval": 6}]


@pytest.fixture(name="smart_wash_params")
def smart_wash_params_trait(
    device: RoborockDevice,
    discover_features_fixture: None,
) -> SmartWashParamsTrait | None:
    """Create a SmartWashParamsTrait instance with mocked dependencies."""
    assert device.v1_properties
    return device.v1_properties.smart_wash_params


@pytest.mark.parametrize(
    ("dock_type_code"),
    dock_types_with_capability("is_washable"),
)
async def test_smart_wash_available(
    smart_wash_params: SmartWashParamsTrait | None,
    mock_rpc_channel: AsyncMock,
    dock_type_code: RoborockDockTypeCode,
) -> None:
    """Test successfully refreshing the smart wash params."""
    assert smart_wash_params is not None

    # Setup mock to return the sample clean summary and clean record
    mock_rpc_channel.send_command.side_effect = [
        SMART_WASH_DATA,
    ]

    # Call the method
    await smart_wash_params.refresh()

    # Verify the RPC calls were made correctly
    mock_rpc_channel.send_command.assert_has_calls(
        [
            call(RoborockCommand.GET_SMART_WASH_PARAMS),
        ]
    )

    # Verify the summary object contains the traits
    assert smart_wash_params.smart_wash == 5
    assert smart_wash_params.wash_interval == 6


@pytest.mark.parametrize("dock_type_code", dock_types_with_capability("is_washable"))
@pytest.mark.parametrize(
    ("mode", "smart_wash"), [(RoborockSmartWashMode.by_time, 0), (RoborockSmartWashMode.by_room, 1)]
)
@pytest.mark.parametrize("wash_interval", [1, 1200])
async def test_set_params(
    smart_wash_params: SmartWashParamsTrait | None,
    mock_rpc_channel: AsyncMock,
    dock_type_code: RoborockDockTypeCode,
    mode: RoborockSmartWashMode,
    smart_wash: int,
    wash_interval: int,
) -> None:
    """Send the explicit pair before refreshing the device-reported values."""
    assert smart_wash_params is not None
    assert smart_wash_params.smart_wash is None
    assert smart_wash_params.wash_interval is None
    mock_rpc_channel.send_command.side_effect = [
        ["ok"],
        [{"smart_wash": 2, "wash_interval": 900}],
    ]

    await smart_wash_params.set_params(mode, wash_interval)

    assert mock_rpc_channel.send_command.call_args_list == [
        call(
            RoborockCommand.SET_SMART_WASH_PARAMS,
            params={"smart_wash": smart_wash, "wash_interval": wash_interval},
        ),
        call(RoborockCommand.GET_SMART_WASH_PARAMS),
    ]
    assert smart_wash_params.smart_wash == 2
    assert smart_wash_params.wash_interval == 900


@pytest.mark.parametrize("dock_type_code", dock_types_with_capability("is_washable"))
@pytest.mark.parametrize(
    "failed_command", [RoborockCommand.SET_SMART_WASH_PARAMS, RoborockCommand.GET_SMART_WASH_PARAMS]
)
async def test_set_params_failure(
    smart_wash_params: SmartWashParamsTrait | None,
    mock_rpc_channel: AsyncMock,
    dock_type_code: RoborockDockTypeCode,
    failed_command: RoborockCommand,
) -> None:
    """A failed SET or refresh propagates without replacing the cached values."""
    assert smart_wash_params is not None
    mock_rpc_channel.send_command.return_value = [{"smart_wash": 2, "wash_interval": 1200}]
    await smart_wash_params.refresh()
    mock_rpc_channel.send_command.reset_mock()
    error = RoborockTimeout("Command timed out")
    expected_calls = [
        call(RoborockCommand.SET_SMART_WASH_PARAMS, params={"smart_wash": 0, "wash_interval": 600}),
    ]
    if failed_command == RoborockCommand.SET_SMART_WASH_PARAMS:
        mock_rpc_channel.send_command.side_effect = error
    else:
        mock_rpc_channel.send_command.side_effect = [["ok"], error]
        expected_calls.append(call(RoborockCommand.GET_SMART_WASH_PARAMS))

    with pytest.raises(RoborockTimeout) as exc_info:
        await smart_wash_params.set_params(RoborockSmartWashMode.by_time, 600)

    assert exc_info.value is error
    assert mock_rpc_channel.send_command.call_args_list == expected_calls
    assert smart_wash_params.smart_wash == 2
    assert smart_wash_params.wash_interval == 1200


@pytest.mark.parametrize("dock_type_code", dock_types_with_capability("is_washable"))
@pytest.mark.parametrize("wash_interval", [0, -1])
async def test_set_params_nonpositive_interval(
    smart_wash_params: SmartWashParamsTrait | None,
    mock_rpc_channel: AsyncMock,
    dock_type_code: RoborockDockTypeCode,
    wash_interval: int,
) -> None:
    """Reject a nonpositive interval before issuing any device command."""
    assert smart_wash_params is not None

    with pytest.raises(ValueError, match="Wash interval must be positive"):
        await smart_wash_params.set_params(RoborockSmartWashMode.by_room, wash_interval)

    mock_rpc_channel.send_command.assert_not_called()
    assert smart_wash_params.smart_wash is None
    assert smart_wash_params.wash_interval is None


@pytest.mark.parametrize("dock_type_code", dock_types_with_capability("is_washable"))
@pytest.mark.parametrize(
    ("smart_wash", "expected_mode"),
    [
        (0, RoborockSmartWashMode.by_time),
        (1, RoborockSmartWashMode.by_room),
        (2, RoborockSmartWashMode.unknown),
    ],
)
async def test_mode(
    smart_wash_params: SmartWashParamsTrait | None,
    mock_rpc_channel: AsyncMock,
    dock_type_code: RoborockDockTypeCode,
    smart_wash: int,
    expected_mode: RoborockSmartWashMode,
) -> None:
    """The reported value maps to a mode while the raw value is preserved."""
    assert smart_wash_params is not None
    assert smart_wash_params.mode is None
    mock_rpc_channel.send_command.return_value = [{"smart_wash": smart_wash, "wash_interval": 1200}]

    await smart_wash_params.refresh()

    assert smart_wash_params.mode is expected_mode
    assert smart_wash_params.smart_wash == smart_wash


@pytest.mark.parametrize("dock_type_code", dock_types_with_capability("is_washable"))
async def test_set_params_rejects_unknown_mode(
    smart_wash_params: SmartWashParamsTrait | None,
    mock_rpc_channel: AsyncMock,
    dock_type_code: RoborockDockTypeCode,
) -> None:
    """An unknown mode cannot be written."""
    assert smart_wash_params is not None

    with pytest.raises(ValueError, match="unknown smart wash mode"):
        await smart_wash_params.set_params(RoborockSmartWashMode.unknown, 1200)

    mock_rpc_channel.send_command.assert_not_called()


@pytest.mark.parametrize(
    ("dock_type_code"),
    dock_types_with_capability("is_washable", expected=False),
)
async def test_unsupported_smart_wash_params(
    smart_wash_params: SmartWashParamsTrait | None, dock_type_code: RoborockDockTypeCode
) -> None:
    """Test successfully refreshing the dock summary."""
    assert smart_wash_params is None
