"""Tests for wheat/grok_tasks.py — Grok API scanning pipeline."""

import json
import os
from datetime import date
from unittest import mock

import pytest

from wheat.grok_tasks import (
    CHANNEL_PROMPTS,
    run_grok_scan,
    run_daily_scans,
    aggregate_scan_results,
    get_pending_intake,
    GROK_RESULTS_DIR,
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


# ---------------------------------------------------------------------------
# run_grok_scan
# ---------------------------------------------------------------------------

class TestRunGrokScan:
    def test_dry_run_returns_none(self, capsys):
        result = run_grok_scan("ch1", _channel(), dry_run=True)
        assert result is None
        out = capsys.readouterr().out
        assert "DRY RUN" in out

    def test_successful_scan(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.grok_tasks.GROK_RESULTS_DIR", str(tmp_path))
        signals = [{"entity": "Bad Dealer", "severity": 4}]
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = (json.dumps(signals), {"prompt_tokens": 50})

        with mock.patch("wheat.grok_tasks.APIProvider", return_value=mock_provider):
            result = run_grok_scan("ch1", _channel())

        assert result["channel_id"] == "ch1"
        assert result["signals"] == signals
        assert len(list(tmp_path.iterdir())) == 1

    def test_fenced_json_extraction(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.grok_tasks.GROK_RESULTS_DIR", str(tmp_path))
        fenced = '```json\n[{"entity": "Y"}]\n```'
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = (fenced, {})

        with mock.patch("wheat.grok_tasks.APIProvider", return_value=mock_provider):
            result = run_grok_scan("ch1", _channel())

        assert result["signals"] == [{"entity": "Y"}]

    def test_generic_fence_extraction(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.grok_tasks.GROK_RESULTS_DIR", str(tmp_path))
        fenced = '```\n[{"entity": "Z"}]\n```'
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = (fenced, {})

        with mock.patch("wheat.grok_tasks.APIProvider", return_value=mock_provider):
            result = run_grok_scan("ch1", _channel())

        assert result["signals"] == [{"entity": "Z"}]

    def test_parse_error_wraps_raw(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.grok_tasks.GROK_RESULTS_DIR", str(tmp_path))
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = ("Not valid JSON", {})

        with mock.patch("wheat.grok_tasks.APIProvider", return_value=mock_provider):
            result = run_grok_scan("ch1", _channel())

        assert result["signals"][0]["parse_error"] is True
        assert "Not valid JSON" in result["signals"][0]["raw_response"]

    def test_provider_exception_returns_none(self):
        mock_provider = mock.MagicMock()
        mock_provider.generate.side_effect = Exception("API key invalid")

        with mock.patch("wheat.grok_tasks.APIProvider", return_value=mock_provider):
            result = run_grok_scan("ch1", _channel())

        assert result is None

    def test_uses_grok_api_provider(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.grok_tasks.GROK_RESULTS_DIR", str(tmp_path))
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = ("[]", {})

        with mock.patch("wheat.grok_tasks.APIProvider", return_value=mock_provider) as mock_cls:
            run_grok_scan("ch1", _channel())

        mock_cls.assert_called_once()
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["api_type"] == "grok"

    def test_uses_grok_model(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.grok_tasks.GROK_RESULTS_DIR", str(tmp_path))
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = ("[]", {})

        with mock.patch("wheat.grok_tasks.APIProvider", return_value=mock_provider):
            run_grok_scan("ch1", _channel())

        call_kwargs = mock_provider.generate.call_args[1]
        assert call_kwargs["model"] == "grok-3-mini"

    def test_saves_metadata(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.grok_tasks.GROK_RESULTS_DIR", str(tmp_path))
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = ("[]", {"tokens": 5})

        with mock.patch("wheat.grok_tasks.APIProvider", return_value=mock_provider):
            result = run_grok_scan("my_ch", _channel(name="My Ch", channel_type="COURT"))

        assert result["channel_name"] == "My Ch"
        assert result["channel_type"] == "COURT"
        files = list(tmp_path.iterdir())
        assert "my_ch" in files[0].name


# ---------------------------------------------------------------------------
# run_daily_scans
# ---------------------------------------------------------------------------

class TestRunDailyScans:
    def test_sunday_returns_empty(self, monkeypatch):
        fake_date = mock.MagicMock()
        fake_date.weekday.return_value = 6
        monkeypatch.setattr("wheat.grok_tasks.date", mock.MagicMock(today=lambda: fake_date))
        results = run_daily_scans()
        assert results == {}

    def test_filters_by_channel(self, monkeypatch):
        channels = {"ch1": _channel(), "ch2": _channel()}
        monkeypatch.setattr("wheat.grok_tasks.load_channels", lambda: channels)
        fake_date = mock.MagicMock()
        fake_date.weekday.return_value = 2
        monkeypatch.setattr("wheat.grok_tasks.date", mock.MagicMock(today=lambda: fake_date))

        with mock.patch("wheat.grok_tasks.run_grok_scan", return_value=None) as mock_scan:
            results = run_daily_scans(channel_filter="ch2")

        assert "ch2" in results
        assert "ch1" not in results

    def test_weekly_skipped_on_non_monday(self, monkeypatch):
        channels = {"weekly_ch": _channel(frequency="weekly")}
        monkeypatch.setattr("wheat.grok_tasks.load_channels", lambda: channels)
        fake_date = mock.MagicMock()
        fake_date.weekday.return_value = 4  # Friday
        monkeypatch.setattr("wheat.grok_tasks.date", mock.MagicMock(today=lambda: fake_date))

        with mock.patch("wheat.grok_tasks.run_grok_scan", return_value=None) as mock_scan:
            run_daily_scans()

        mock_scan.assert_not_called()

    def test_weekly_runs_on_monday(self, monkeypatch):
        channels = {"weekly_ch": _channel(frequency="weekly")}
        monkeypatch.setattr("wheat.grok_tasks.load_channels", lambda: channels)
        fake_date = mock.MagicMock()
        fake_date.weekday.return_value = 0  # Monday
        monkeypatch.setattr("wheat.grok_tasks.date", mock.MagicMock(today=lambda: fake_date))

        with mock.patch("wheat.grok_tasks.run_grok_scan", return_value=None) as mock_scan:
            run_daily_scans()

        mock_scan.assert_called_once()


# ---------------------------------------------------------------------------
# aggregate_scan_results
# ---------------------------------------------------------------------------

class TestAggregateScanResults:
    def test_empty(self):
        summary, by_field = aggregate_scan_results({})
        assert "Total signals: 0" in summary
        assert by_field == {}

    def test_with_signals(self):
        results = {
            "ch1": {"signals": [{"a": 1}], "target_fields": ["tow_companies"]},
            "ch2": {"signals": [{"b": 2}, {"c": 3}], "target_fields": ["auto_repair"]},
        }
        summary, by_field = aggregate_scan_results(results)
        assert "Total signals: 3" in summary
        assert "Grok" in summary
        assert len(by_field["tow_companies"]) == 1
        assert len(by_field["auto_repair"]) == 2

    def test_null_results_skipped(self):
        summary, by_field = aggregate_scan_results({"ch1": None})
        assert "Total signals: 0" in summary

    def test_non_list_signals_skipped(self):
        results = {"ch1": {"signals": "broken", "target_fields": ["x"]}}
        summary, by_field = aggregate_scan_results(results)
        assert "Total signals: 0" in summary


# ---------------------------------------------------------------------------
# get_pending_intake
# ---------------------------------------------------------------------------

class TestGetPendingIntake:
    def test_no_directory(self, monkeypatch):
        monkeypatch.setattr("wheat.grok_tasks.GROK_RESULTS_DIR", "/nonexistent/path")
        assert get_pending_intake() == []

    def test_lists_json_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.grok_tasks.GROK_RESULTS_DIR", str(tmp_path))
        (tmp_path / "scan1.json").write_text("{}")
        (tmp_path / "scan2.json").write_text("{}")
        (tmp_path / "notes.txt").write_text("skip")

        files = get_pending_intake()
        assert len(files) == 2

    def test_sorted_reverse(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.grok_tasks.GROK_RESULTS_DIR", str(tmp_path))
        (tmp_path / "a.json").write_text("{}")
        (tmp_path / "z.json").write_text("{}")

        files = get_pending_intake()
        assert "z.json" in files[0]
