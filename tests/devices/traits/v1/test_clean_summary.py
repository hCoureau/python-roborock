"""Tests for the CleanSummary class."""

from copy import deepcopy
from datetime import UTC, datetime
from unittest.mock import AsyncMock, call

import pytest

from roborock.data import CleanSummary
from roborock.devices.device import RoborockDevice
from roborock.devices.traits.v1.clean_summary import CleanSummaryTrait
from roborock.exceptions import RoborockException, RoborockParsingException
from roborock.roborock_typing import RoborockCommand
from tests.mock_data import CLEAN_RECORD

CLEAN_SUMMARY_DATA = [
    1442559,
    24258125000,
    296,
    [
        1756848207,
        1754930385,
        1753203976,
        1752183435,
        1747427370,
        1746204046,
        1745601543,
        1744387080,
        1743528522,
        1742489154,
        1741022299,
        1740433682,
        1739902516,
        1738875106,
        1738864366,
        1738620067,
        1736873889,
        1736197544,
        1736121269,
        1734458038,
    ],
]

CLEAN_RECORD_DATA = [
    [
        1738864366,
        1738868964,
        4358,
        81122500,
        0,
        0,
        1,
        1,
        21,
    ]
]


@pytest.fixture
def clean_summary_trait(device: RoborockDevice) -> CleanSummaryTrait:
    """Create a DoNotDisturbTrait instance with mocked dependencies."""
    assert device.v1_properties
    return device.v1_properties.clean_summary


@pytest.fixture
def sample_clean_summary() -> CleanSummary:
    """Create a sample CleanSummary for testing."""
    return CleanSummary(
        clean_area=100,
        clean_time=3600,
    )


async def test_get_clean_summary_success(
    clean_summary_trait: CleanSummaryTrait, mock_rpc_channel: AsyncMock, sample_clean_summary: CleanSummary
) -> None:
    """Test successfully getting clean summary."""
    # Setup mock to return the sample clean summary
    mock_rpc_channel.send_command.side_effect = [CLEAN_SUMMARY_DATA, CLEAN_RECORD_DATA]

    # Call the method
    await clean_summary_trait.refresh()

    # Verify the result
    assert clean_summary_trait.clean_area == 24258125000
    assert clean_summary_trait.clean_time == 1442559
    assert clean_summary_trait.square_meter_clean_area == 24258.1
    assert clean_summary_trait.clean_count == 296
    assert clean_summary_trait.records
    assert len(clean_summary_trait.records) == 20
    assert clean_summary_trait.records[0] == 1756848207
    assert clean_summary_trait.last_clean_record
    assert clean_summary_trait.last_clean_record.begin == 1738864366

    # Verify the RPC call was made correctly
    mock_rpc_channel.send_command.assert_has_calls(
        [call(RoborockCommand.GET_CLEAN_SUMMARY), call(RoborockCommand.GET_CLEAN_RECORD, params=[1756848207])]
    )


@pytest.mark.parametrize(
    "records",
    [
        [1700000000, 1700000400, 1700000800],
        [1700000800, 1700000400, 1700000000],
        [1700000400, 1700000800, 1700000000],
        [1700000800],
    ],
    ids=["ascending", "descending", "unordered", "single"],
)
async def test_get_clean_summary_latest_record(
    clean_summary_trait: CleanSummaryTrait, mock_rpc_channel: AsyncMock, records: list[int]
) -> None:
    """Load the latest cleaning regardless of the order returned by the device."""
    mock_rpc_channel.send_command.side_effect = [
        [3600, 1000000, len(records), records],
        [[1700000800, 1700000900, 100, 1000000]],
    ]

    await clean_summary_trait.refresh()

    assert mock_rpc_channel.send_command.call_args_list == [
        call(RoborockCommand.GET_CLEAN_SUMMARY),
        call(RoborockCommand.GET_CLEAN_RECORD, params=[1700000800]),
    ]
    assert clean_summary_trait.records == records
    assert clean_summary_trait.last_clean_record is not None
    assert clean_summary_trait.last_clean_record.begin == 1700000800
    assert clean_summary_trait.last_clean_record.end == 1700000900


async def test_get_clean_summary_clean_time_only(
    clean_summary_trait: CleanSummaryTrait, mock_rpc_channel: AsyncMock, sample_clean_summary: CleanSummary
) -> None:
    """Test successfully getting clean summary where the response only has the clean time."""

    mock_rpc_channel.send_command.return_value = [1442559]

    # Call the method
    await clean_summary_trait.refresh()

    # Verify the result
    assert clean_summary_trait.clean_area is None
    assert clean_summary_trait.clean_time == 1442559
    assert clean_summary_trait.square_meter_clean_area is None
    assert clean_summary_trait.clean_count is None
    assert not clean_summary_trait.records

    # Verify the RPC call was made correctly
    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.GET_CLEAN_SUMMARY)


async def test_get_clean_summary_propagates_exception(
    clean_summary_trait: CleanSummaryTrait, mock_rpc_channel: AsyncMock
) -> None:
    """Test that exceptions from RPC channel are propagated in get_clean_summary."""

    # Setup mock to raise an exception
    mock_rpc_channel.send_command.side_effect = RoborockException("Communication error")

    # Verify the exception is propagated
    with pytest.raises(RoborockException, match="Communication error"):
        await clean_summary_trait.refresh()


async def test_get_clean_record_success(
    clean_summary_trait: CleanSummaryTrait,
    mock_rpc_channel: AsyncMock,
) -> None:
    """Test successfully getting the last clean record."""
    # Setup mock to return the sample clean summary and clean record
    mock_rpc_channel.send_command.side_effect = [
        CLEAN_RECORD_DATA,
    ]

    # Call the method
    clean_record = await clean_summary_trait.get_clean_record(1738864366)

    # Verify the result
    assert clean_record.begin == 1738864366
    assert clean_record.end == 1738868964
    assert clean_record.duration == 4358
    assert clean_record.area == 81122500
    assert clean_record.complete is None
    assert clean_record.start_type is None
    assert clean_record.clean_type is None
    assert clean_record.finish_reason is None

    # Verify the RPC calls were made correctly
    mock_rpc_channel.send_command.assert_has_calls(
        [
            call(RoborockCommand.GET_CLEAN_RECORD, params=[1738864366]),
        ]
    )


@pytest.mark.parametrize("response", [[], [[]]], ids=["empty", "wrapped-empty"])
async def test_get_clean_record_empty_response(
    clean_summary_trait: CleanSummaryTrait, mock_rpc_channel: AsyncMock, response: list
) -> None:
    """Report empty records through the public parsing exception boundary."""
    mock_rpc_channel.send_command.return_value = response

    with pytest.raises(RoborockParsingException, match="GET_CLEAN_RECORD") as exc:
        await clean_summary_trait.get_clean_record(1738864366)

    assert isinstance(exc.value.__cause__, ValueError)
    assert f"Payload: {response!r}" in str(exc.value)
    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.GET_CLEAN_RECORD, params=[1738864366])


@pytest.mark.parametrize(
    "response",
    [
        [CLEAN_RECORD],
        [
            {
                "begin": 1700000000,
                "end": 1700000100,
                "duration": 100,
                "area": 1000000,
                "avoid_count": 1,
                "wash_count": 1,
            },
            {
                "begin": 1700000200,
                "end": 1700000400,
                "duration": 200,
                "area": 2000000,
                "avoid_count": 2,
                "wash_count": 2,
            },
        ],
    ],
    ids=["wrapped-dict", "multi-phase"],
)
async def test_get_clean_record_structured_responses(
    clean_summary_trait: CleanSummaryTrait, mock_rpc_channel: AsyncMock, response: list[dict]
) -> None:
    """Keep wrapped and multi-phase records working through the public API."""
    mock_rpc_channel.send_command.return_value = response

    record = await clean_summary_trait.get_clean_record(1738864366)

    assert record.begin == response[0]["begin"]
    assert record.end == response[-1]["end"]


@pytest.mark.parametrize("phase_count", [2, 3])
async def test_get_clean_record_phase_totals(
    clean_summary_trait: CleanSummaryTrait, mock_rpc_channel: AsyncMock, phase_count: int
) -> None:
    """Combine raw phase totals while retaining first/last phase metadata."""
    phases = [
        {
            "begin": 1700000000 + index * 200,
            "end": 1700000100 + index * 200,
            "duration": 100,
            "area": 1040000,
            "avoid_count": index,
            "wash_count": 1,
            "start_type": index + 1,
            "error": index,
            "complete": index,
            "clean_type": index + 1,
            "finish_reason": 56,
            "dust_collection_status": index,
            "map_flag": index,
        }
        for index in range(phase_count)
    ]
    original = deepcopy(phases)
    mock_rpc_channel.send_command.return_value = phases

    record = await clean_summary_trait.get_clean_record(1700000000)

    assert record.begin == phases[0]["begin"]
    assert record.begin_datetime == datetime.fromtimestamp(phases[0]["begin"], tz=UTC)
    assert record.start_type == phases[0]["start_type"]
    assert record.end == phases[-1]["end"]
    assert record.end_datetime == datetime.fromtimestamp(phases[-1]["end"], tz=UTC)
    assert record.duration == 100 * phase_count
    assert record.area == 1040000 * phase_count
    assert record.square_meter_area == round(1.04 * phase_count, 1)
    assert record.avoid_count == sum(range(phase_count))
    assert record.wash_count == phase_count
    assert record.error == phases[-1]["error"]
    assert record.complete == phases[-1]["complete"]
    assert record.clean_type == phases[-1]["clean_type"]
    assert record.finish_reason == phases[-1]["finish_reason"]
    assert record.dust_collection_status == phases[-1]["dust_collection_status"]
    assert record.map_flag == phases[-1]["map_flag"]
    assert phases == original
    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.GET_CLEAN_RECORD, params=[1700000000])


@pytest.mark.parametrize("field", ["duration", "area", "avoid_count", "wash_count"])
@pytest.mark.parametrize(
    ("values", "expected"),
    [([None, 4, None], 4), ([None, None, None], None), ([0, None, 0], 0)],
)
async def test_get_clean_record_missing_phase_values(
    clean_summary_trait: CleanSummaryTrait,
    mock_rpc_channel: AsyncMock,
    field: str,
    values: list[int | None],
    expected: int | None,
) -> None:
    """Sum reported values without inventing a value for an entirely absent field."""
    phases = [{"begin": 1700000000 + index * 100, field: value} for index, value in enumerate(values)]
    mock_rpc_channel.send_command.return_value = phases

    record = await clean_summary_trait.get_clean_record(1700000000)

    assert getattr(record, field) == expected
    if field == "area" and expected is None:
        assert record.square_meter_area is None


@pytest.mark.parametrize(
    "response",
    [[{"begin": 1700000000}, 42], [42, {"begin": 1700000000}], [42, {"begin": 1700000000}, 43]],
)
async def test_get_clean_record_mixed_phase_formats(
    clean_summary_trait: CleanSummaryTrait, mock_rpc_channel: AsyncMock, response: list
) -> None:
    """Reject mixed phase formats through the contextual public exception."""
    original = deepcopy(response)
    mock_rpc_channel.send_command.return_value = response

    with pytest.raises(RoborockParsingException, match="GET_CLEAN_RECORD") as exc:
        await clean_summary_trait.get_clean_record(1700000000)

    assert isinstance(exc.value.__cause__, ValueError)
    assert f"Payload: {response!r}" in str(exc.value)
    assert response == original


async def test_get_clean_record_dict_response(
    clean_summary_trait: CleanSummaryTrait,
    mock_rpc_channel: AsyncMock,
) -> None:
    """Test successfully getting the last clean record as a dictionary."""
    # Setup mock to return the sample clean summary and clean record
    mock_rpc_channel.send_command.side_effect = [
        CLEAN_RECORD,
    ]

    # Call the method
    clean_record = await clean_summary_trait.get_clean_record(1738864366)

    # Verify the result
    assert clean_record.begin == 1672543330
    assert clean_record.end == 1672544638
    assert clean_record.duration == 1176
    assert clean_record.area == 20965000
    assert clean_record.complete == 1
    assert clean_record.start_type == 2
    assert clean_record.clean_type == 3
    assert clean_record.finish_reason == 56
    assert clean_record.dust_collection_status == 1
    assert clean_record.avoid_count == 19
    assert clean_record.wash_count == 2
    assert clean_record.map_flag == 0

    # Verify the RPC calls were made correctly
    mock_rpc_channel.send_command.assert_has_calls(
        [
            call(RoborockCommand.GET_CLEAN_RECORD, params=[1738864366]),
        ]
    )


async def test_get_clean_summary_no_records(
    clean_summary_trait: CleanSummaryTrait, mock_rpc_channel: AsyncMock
) -> None:
    """Test successfully getting clean summary with no records."""
    # Setup mock to return the sample clean summary with no records
    mock_rpc_channel.send_command.return_value = [
        1442559,
        24258125000,
        296,
        [],
    ]

    # Call the method
    await clean_summary_trait.refresh()

    # Verify the result
    assert clean_summary_trait.clean_area == 24258125000
    assert clean_summary_trait.clean_time == 1442559
    assert clean_summary_trait.clean_count == 296
    assert not clean_summary_trait.records
    assert clean_summary_trait.last_clean_record is None

    # Verify the RPC call was made correctly
    mock_rpc_channel.send_command.assert_called_once_with(RoborockCommand.GET_CLEAN_SUMMARY)
