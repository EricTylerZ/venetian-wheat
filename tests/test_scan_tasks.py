"""Tests for wheat/scan_tasks.py — Claude Code Sonnet scanning pipeline."""

import json
import os
from datetime import date
from unittest import mock

import pytest

from wheat.scan_tasks import (
    CHANNEL_PROMPTS,
    run_channel_scan,
    run_daily_scans,
    aggregate_scan_results,
    get_pending_intake,
    SCAN_RESULTS_DIR,
)


def _channel(name="Test Channel", channel_type="NEWS", sources=None, fields=None, frequency="daily"):
    return {
        "name": name,
        "channel_type": channel_type,
        "sources": sources or ["https://example.com"],
        "fields": fields or ["tow_companies"],
        "frequency": frequency,
    }


# ---------------------------------------------------------------------------
# CHANNEL_PROMPTS
# ---------------------------------------------------------------------------

class TestChannelPrompts:
    def test_all_types_present(self):
        expected = {"REVIEWS", "REGULATORY", "NEWS", "SOCIAL", "PUBLIC_RECORDS", "COURT"}
        assert set(CHANNEL_PROMPTS.keys()) == expected

    def test_all_have_sources_placeholder(self):
        for ctype, prompt in CHANNEL_PROMPTS.items():
            assert "{sources}" in prompt, f"{ctype} missing {{sources}}"

    def test_all_request_json_output(self):
        for ctype, prompt in CHANNEL_PROMPTS.items():
            assert "JSON" in prompt, f"{ctype} doesn't mention JSON"


# ---------------------------------------------------------------------------
# run_channel_scan
# ---------------------------------------------------------------------------

class TestRunChannelScan:
    def test_dry_run_returns_none(self, capsys):
        result = run_channel_scan("ch1", _channel(), dry_run=True)
        assert result is None
        out = capsys.readouterr().out
        assert "DRY RUN" in out

    def test_dry_run_shows_channel_info(self, capsys):
        ch = _channel(name="BBB Reviews", channel_type="REVIEWS", sources=["a", "b"], fields=["tow_companies", "auto_repair"])
        run_channel_scan("bbb", ch, dry_run=True)
        out = capsys.readouterr().out
        assert "BBB Reviews" in out
        assert "REVIEWS" in out
        assert "2" in out  # sources count

    def test_successful_scan(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.scan_tasks.SCAN_RESULTS_DIR", str(tmp_path))
        signals = [{"entity": "Bad Tow", "severity": 3}]
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = (json.dumps(signals), {"prompt_tokens": 50, "completion_tokens": 100})

        with mock.patch("wheat.scan_tasks.ClaudeCodeProvider", return_value=mock_provider):
            result = run_channel_scan("ch1", _channel())

        assert result["channel_id"] == "ch1"
        assert result["signals"] == signals
        assert len(list(tmp_path.iterdir())) == 1

    def test_fenced_json_extraction(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.scan_tasks.SCAN_RESULTS_DIR", str(tmp_path))
        fenced = '```json\n[{"entity": "X"}]\n```'
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = (fenced, {})

        with mock.patch("wheat.scan_tasks.ClaudeCodeProvider", return_value=mock_provider):
            result = run_channel_scan("ch1", _channel())

        assert result["signals"] == [{"entity": "X"}]

    def test_parse_error_wraps_raw(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.scan_tasks.SCAN_RESULTS_DIR", str(tmp_path))
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = ("Not JSON at all", {})

        with mock.patch("wheat.scan_tasks.ClaudeCodeProvider", return_value=mock_provider):
            result = run_channel_scan("ch1", _channel())

        assert result["signals"][0]["parse_error"] is True

    def test_provider_exception_returns_none(self):
        mock_provider = mock.MagicMock()
        mock_provider.generate.side_effect = Exception("timeout")

        with mock.patch("wheat.scan_tasks.ClaudeCodeProvider", return_value=mock_provider):
            result = run_channel_scan("ch1", _channel())

        assert result is None

    def test_unknown_type_falls_back_to_news(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.scan_tasks.SCAN_RESULTS_DIR", str(tmp_path))
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = ("[]", {})

        with mock.patch("wheat.scan_tasks.ClaudeCodeProvider", return_value=mock_provider):
            run_channel_scan("ch1", _channel(channel_type="UNKNOWN_TYPE"))

        prompt_used = mock_provider.generate.call_args[1]["prompt"]
        # Should use NEWS template (mentions "local news")
        assert "local news" in prompt_used.lower() or "stories" in prompt_used.lower()

    def test_saves_result_file_with_metadata(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.scan_tasks.SCAN_RESULTS_DIR", str(tmp_path))
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = ("[]", {"tokens": 10})

        with mock.patch("wheat.scan_tasks.ClaudeCodeProvider", return_value=mock_provider):
            result = run_channel_scan("my_ch", _channel(name="My Channel", channel_type="REVIEWS"))

        assert result["channel_name"] == "My Channel"
        assert result["channel_type"] == "REVIEWS"
        assert result["provider"] == "claude_code_sonnet"
        # Verify file on disk
        files = list(tmp_path.iterdir())
        assert len(files) == 1
        assert "my_ch" in files[0].name


# ---------------------------------------------------------------------------
# run_daily_scans
# ---------------------------------------------------------------------------

class TestRunDailyScans:
    def test_sunday_returns_empty(self, monkeypatch):
        # Mock date.today() to return a Sunday
        fake_date = mock.MagicMock()
        fake_date.weekday.return_value = 6
        fake_date.isoformat.return_value = "2026-03-15"
        monkeypatch.setattr("wheat.scan_tasks.date", mock.MagicMock(today=lambda: fake_date))
        results = run_daily_scans()
        assert results == {}

    def test_filters_by_channel(self, monkeypatch):
        channels = {
            "ch1": _channel(name="Ch1"),
            "ch2": _channel(name="Ch2"),
        }
        monkeypatch.setattr("wheat.scan_tasks.load_channels", lambda: channels)
        fake_date = mock.MagicMock()
        fake_date.weekday.return_value = 1  # Tuesday
        monkeypatch.setattr("wheat.scan_tasks.date", mock.MagicMock(today=lambda: fake_date))

        with mock.patch("wheat.scan_tasks.run_channel_scan", return_value={"signals": []}) as mock_scan:
            results = run_daily_scans(channel_filter="ch1")

        assert "ch1" in results
        assert "ch2" not in results

    def test_runs_daily_channels(self, monkeypatch):
        channels = {
            "daily_ch": _channel(frequency="daily"),
            "weekly_ch": _channel(frequency="weekly"),
        }
        monkeypatch.setattr("wheat.scan_tasks.load_channels", lambda: channels)
        fake_date = mock.MagicMock()
        fake_date.weekday.return_value = 3  # Thursday (not Monday)
        monkeypatch.setattr("wheat.scan_tasks.date", mock.MagicMock(today=lambda: fake_date))

        with mock.patch("wheat.scan_tasks.run_channel_scan", return_value=None) as mock_scan:
            results = run_daily_scans()

        # Daily runs, weekly skipped (not Monday)
        assert mock_scan.call_count == 1

    def test_weekly_runs_on_monday(self, monkeypatch):
        channels = {
            "weekly_ch": _channel(frequency="weekly"),
        }
        monkeypatch.setattr("wheat.scan_tasks.load_channels", lambda: channels)
        fake_date = mock.MagicMock()
        fake_date.weekday.return_value = 0  # Monday
        monkeypatch.setattr("wheat.scan_tasks.date", mock.MagicMock(today=lambda: fake_date))

        with mock.patch("wheat.scan_tasks.run_channel_scan", return_value=None) as mock_scan:
            results = run_daily_scans()

        assert mock_scan.call_count == 1


# ---------------------------------------------------------------------------
# aggregate_scan_results
# ---------------------------------------------------------------------------

class TestAggregateScanResults:
    def test_empty_results(self):
        summary, by_field = aggregate_scan_results({})
        assert "Total signals: 0" in summary
        assert by_field == {}

    def test_null_results_skipped(self):
        summary, by_field = aggregate_scan_results({"ch1": None, "ch2": {}})
        assert "Total signals: 0" in summary

    def test_counts_signals(self):
        results = {
            "ch1": {
                "signals": [{"a": 1}, {"b": 2}],
                "target_fields": ["tow_companies"],
            },
            "ch2": {
                "signals": [{"c": 3}],
                "target_fields": ["auto_repair"],
            },
        }
        summary, by_field = aggregate_scan_results(results)
        assert "Total signals: 3" in summary
        assert len(by_field["tow_companies"]) == 2
        assert len(by_field["auto_repair"]) == 1

    def test_multi_field_signals(self):
        results = {
            "ch1": {
                "signals": [{"x": 1}],
                "target_fields": ["tow_companies", "auto_repair"],
            },
        }
        summary, by_field = aggregate_scan_results(results)
        assert len(by_field["tow_companies"]) == 1
        assert len(by_field["auto_repair"]) == 1

    def test_non_list_signals_skipped(self):
        results = {
            "ch1": {"signals": "not a list", "target_fields": ["x"]},
        }
        summary, by_field = aggregate_scan_results(results)
        assert "Total signals: 0" in summary


# ---------------------------------------------------------------------------
# get_pending_intake
# ---------------------------------------------------------------------------

class TestGetPendingIntake:
    def test_no_directory(self, monkeypatch):
        monkeypatch.setattr("wheat.scan_tasks.SCAN_RESULTS_DIR", "/nonexistent/path")
        assert get_pending_intake() == []

    def test_lists_json_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.scan_tasks.SCAN_RESULTS_DIR", str(tmp_path))
        (tmp_path / "ch1_20260313.json").write_text("{}")
        (tmp_path / "ch2_20260313.json").write_text("{}")
        (tmp_path / "readme.txt").write_text("ignore me")

        files = get_pending_intake()
        assert len(files) == 2
        assert all(f.endswith(".json") for f in files)

    def test_sorted_reverse(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.scan_tasks.SCAN_RESULTS_DIR", str(tmp_path))
        (tmp_path / "a_20260301.json").write_text("{}")
        (tmp_path / "b_20260302.json").write_text("{}")

        files = get_pending_intake()
        assert "b_20260302" in files[0]
