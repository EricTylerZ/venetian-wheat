"""Tests for wheat/token_steward.py — daily token usage tracking."""

import json
import os
import pytest
from datetime import datetime, timedelta
from unittest import mock

from wheat.token_steward import TokenSteward


@pytest.fixture
def steward(tmp_path, monkeypatch):
    """Create a TokenSteward with isolated file paths."""
    config = {"token_period": "daily"}
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))

    # Patch os.path.realpath so the config path resolves to tmp_path
    _real_realpath = os.path.realpath
    monkeypatch.setattr(
        "wheat.token_steward.os.path.realpath",
        lambda p: str(tmp_path / "wheat" / "token_steward.py") if "token_steward" in str(p) else _real_realpath(p),
    )
    # Create the parent dirs so dirname works
    (tmp_path / "wheat").mkdir(exist_ok=True)

    # Redirect token_log.json to tmp_path
    monkeypatch.chdir(tmp_path)

    return TokenSteward()


class TestTokenStewardInit:
    def test_initializes_with_zero_tokens(self, steward):
        assert steward.data["prompt_tokens"] == 0
        assert steward.data["completion_tokens"] == 0
        assert steward.data["total_tokens"] == 0

    def test_has_period_start_and_end(self, steward):
        start = datetime.fromisoformat(steward.data["period_start"])
        end = datetime.fromisoformat(steward.data["period_end"])
        assert end - start == timedelta(days=1)

    def test_period_starts_at_midnight(self, steward):
        start = datetime.fromisoformat(steward.data["period_start"])
        assert start.hour == 0
        assert start.minute == 0
        assert start.second == 0


class TestCanWater:
    def test_always_returns_true(self, steward):
        assert steward.can_water(1000) is True
        assert steward.can_water(999999) is True

    def test_with_is_output_flag(self, steward):
        assert steward.can_water(500, is_output=True) is True


class TestWaterUsed:
    def test_accumulates_tokens(self, steward):
        steward.water_used(100, 50)
        assert steward.data["prompt_tokens"] == 100
        assert steward.data["completion_tokens"] == 50
        assert steward.data["total_tokens"] == 150

    def test_multiple_calls_accumulate(self, steward):
        steward.water_used(100, 50)
        steward.water_used(200, 75)
        assert steward.data["prompt_tokens"] == 300
        assert steward.data["completion_tokens"] == 125
        assert steward.data["total_tokens"] == 425

    def test_saves_to_file(self, steward, tmp_path):
        steward.water_used(10, 5)
        log_path = tmp_path / "token_log.json"
        assert log_path.exists()
        saved = json.loads(log_path.read_text())
        assert saved["total_tokens"] == 15

    def test_resets_on_period_expiry(self, steward):
        steward.water_used(100, 50)
        # Simulate expired period
        steward.data["period_end"] = (datetime.now() - timedelta(hours=1)).isoformat()
        steward.water_used(10, 5)
        # Should have reset then added new values
        assert steward.data["prompt_tokens"] == 10
        assert steward.data["completion_tokens"] == 5
        assert steward.data["total_tokens"] == 15


class TestLoadLog:
    def test_loads_existing_valid_log(self, steward, tmp_path):
        # Write a log with existing usage
        log_data = {
            "period_start": datetime.now().replace(hour=0, minute=0, second=0).isoformat(),
            "period_end": (datetime.now() + timedelta(hours=12)).isoformat(),
            "prompt_tokens": 500,
            "completion_tokens": 200,
            "total_tokens": 700,
        }
        (tmp_path / "token_log.json").write_text(json.dumps(log_data))

        steward.load_log()
        assert steward.data["total_tokens"] == 700

    def test_resets_on_expired_log(self, steward, tmp_path):
        log_data = {
            "period_start": (datetime.now() - timedelta(days=2)).isoformat(),
            "period_end": (datetime.now() - timedelta(days=1)).isoformat(),
            "prompt_tokens": 999,
            "completion_tokens": 999,
            "total_tokens": 1998,
        }
        (tmp_path / "token_log.json").write_text(json.dumps(log_data))

        steward.load_log()
        assert steward.data["total_tokens"] == 0

    def test_resets_on_corrupt_json(self, steward, tmp_path):
        (tmp_path / "token_log.json").write_text("not json{{{")
        steward.load_log()
        assert steward.data["total_tokens"] == 0

    def test_resets_on_invalid_period_end(self, steward, tmp_path):
        log_data = {"period_end": 12345, "total_tokens": 999}
        (tmp_path / "token_log.json").write_text(json.dumps(log_data))
        steward.load_log()
        assert steward.data["total_tokens"] == 0

    def test_creates_file_if_not_exists(self, steward, tmp_path):
        log_path = tmp_path / "token_log.json"
        if log_path.exists():
            log_path.unlink()
        steward.load_log()
        assert log_path.exists()


class TestSaveLog:
    def test_persists_data(self, steward, tmp_path):
        steward.data["total_tokens"] = 42
        steward.save_log()
        saved = json.loads((tmp_path / "token_log.json").read_text())
        assert saved["total_tokens"] == 42
