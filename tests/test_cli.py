"""Tests for the command line interface."""

import json
from collections.abc import Generator
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from click.testing import CliRunner

from roborock.cli import ConnectionCache, RoborockContext, cli, set_child_lock
from roborock.data import HomeDataSchedule, UserData
from roborock.exceptions import RoborockException
from roborock.testing import FakeRoborockCloud, V1VacuumSimulator
from roborock.testing.v1_simulator import DEFAULT_APP_INIT
from roborock.web_api import RoborockApiClient
from tests.mock_data import USER_DATA, USER_EMAIL


@pytest.fixture(autouse=True)
def isolated_login(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Use temporary cached credentials so commands never load the user's login."""
    login_file = tmp_path / ".roborock"
    monkeypatch.setattr(RoborockContext, "roborock_file", login_file)
    monkeypatch.setattr(RoborockContext, "roborock_cache_file", tmp_path / ".roborock.cache")
    login_file.write_text(
        json.dumps(ConnectionCache(user_data=UserData.from_dict(USER_DATA), email=USER_EMAIL).as_dict()),
        encoding="utf-8",
    )


@pytest.fixture
def mock_api(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Replace the cloud client, including all asynchronous network operations."""
    factory = Mock(return_value=Mock(spec=RoborockApiClient))
    monkeypatch.setattr("roborock.cli.RoborockApiClient", factory)
    return factory


@pytest.fixture
def job_data() -> dict[str, Any]:
    """A schedule including model-specific cleaning settings."""
    return {
        "id": 3878757,
        "cron": "05 10 * * ?",
        "repeated": True,
        "enabled": False,
        "param": {"mapId": 0, "rooms": [1, 2], "custom_key": {"id": 7, "value": None}},
    }


def test_update_job(mock_api: Mock, tmp_path: Path, job_data: dict[str, Any]) -> None:
    """The CLI parses JSON into a schedule and calls the API using cached credentials."""
    job_file = tmp_path / "job.json"
    job_file.write_text(json.dumps(job_data), encoding="utf-8")

    result = CliRunner().invoke(cli, ["update-job", "--device_id", "123456", "--job-file", str(job_file)])

    assert result.exit_code == 0, result.output
    assert result.output == "Updated job 3878757 for device 123456\n"
    mock_api.assert_called_once_with(USER_EMAIL)
    mock_api.return_value.update_job.assert_awaited_once_with(
        UserData.from_dict(USER_DATA), "123456", HomeDataSchedule(**job_data)
    )


def test_update_job_invalid_json(mock_api: Mock, tmp_path: Path) -> None:
    """A JSON parsing failure is reported without calling the cloud API."""
    job_file = tmp_path / "job.json"
    job_file.write_text("[", encoding="utf-8")

    result = CliRunner().invoke(cli, ["update-job", "--device_id", "123456", "--job-file", str(job_file)])

    assert result.exit_code == 1
    assert "Error: Expecting value" in result.output
    mock_api.assert_not_called()


def test_update_job_api_error(mock_api: Mock, tmp_path: Path, job_data: dict[str, Any]) -> None:
    """A cloud rejection is reported with an unsuccessful command exit."""
    mock_api.return_value.update_job.side_effect = RoborockException("Job not found")
    job_file = tmp_path / "job.json"
    job_file.write_text(json.dumps(job_data), encoding="utf-8")

    result = CliRunner().invoke(cli, ["update-job", "--device_id", "123456", "--job-file", str(job_file)])

    assert result.exit_code == 1
    assert result.output == "Error: Job not found\n"
    mock_api.return_value.update_job.assert_awaited_once()


@pytest.fixture
def fake_device() -> Generator[V1VacuumSimulator, None, None]:
    """A simulated V1 vacuum, with child lock support, served by a fake cloud."""
    # Feature bit 256 is is_set_child_supported.
    device = V1VacuumSimulator(
        app_init=replace(DEFAULT_APP_INIT, new_feature_info=DEFAULT_APP_INIT.new_feature_info | 256),
    )

    def set_child_lock_status(params: dict[str, int]) -> str:
        device.status.lock_status = params["lock_status"]
        return "ok"

    device.custom_handlers = {
        "get_child_lock_status": lambda params: {"lock_status": device.status.lock_status},
        "set_child_lock_status": set_child_lock_status,
    }
    cloud = FakeRoborockCloud(user_data=UserData.from_dict(USER_DATA))
    cloud.add_device(device)
    with cloud.patch_device_manager():
        yield device


def test_clean_record(fake_device: V1VacuumSimulator) -> None:
    """The command prints the last clean record from the clean summary."""
    result = CliRunner().invoke(cli, ["clean-record", "--device_id", fake_device.duid])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == fake_device.last_clean_record.as_dict()


def test_clean_record_no_records(fake_device: V1VacuumSimulator) -> None:
    """The command reports when the device has no clean records."""
    fake_device.clean_summary.records = []

    result = CliRunner().invoke(cli, ["clean-record", "--device_id", fake_device.duid])

    assert result.exit_code == 0, result.output
    assert result.output == "No clean record available\n"


@pytest.mark.parametrize(("enabled", "lock_status"), [("true", 1), ("false", 0)])
def test_set_child_lock(fake_device: V1VacuumSimulator, enabled: str, lock_status: int) -> None:
    """The session command sets the child lock on the device."""
    fake_device.status.lock_status = 1 - lock_status

    result = CliRunner().invoke(
        set_child_lock, ["--device_id", fake_device.duid, "--enabled", enabled], obj=RoborockContext()
    )

    assert result.exit_code == 0, result.output
    assert fake_device.status.lock_status == lock_status
