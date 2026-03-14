"""Tests for wheat/analyst.py — analyst brain, scan correlation, field guidance, briefing."""

import json
import os
from datetime import date, datetime
from unittest import mock

import pytest

from wheat.analyst import (
    get_analyst_provider,
    correlate_scans,
    build_field_guidance,
    synthesize_briefing,
    CORRELATION_PROMPT,
    BRIEFING_PROMPT,
)


# ---------------------------------------------------------------------------
# get_analyst_provider
# ---------------------------------------------------------------------------

class TestGetAnalystProvider:
    def test_default_returns_claude_code_provider(self):
        provider = get_analyst_provider()
        from wheat.providers import ClaudeCodeProvider
        assert isinstance(provider, ClaudeCodeProvider)

    def test_config_analyst_model(self):
        provider = get_analyst_provider({"analyst_model": "custom-model"})
        from wheat.providers import ClaudeCodeProvider
        assert isinstance(provider, ClaudeCodeProvider)

    def test_config_analyst_provider_override(self):
        with mock.patch("wheat.analyst.get_provider") as mock_gp:
            mock_gp.return_value = mock.MagicMock()
            provider = get_analyst_provider({"analyst_provider": {"llm_api": "venice"}})
            mock_gp.assert_called_once_with({"llm_api": "venice"})

    def test_none_config_uses_default(self):
        provider = get_analyst_provider(None)
        from wheat.providers import ClaudeCodeProvider
        assert isinstance(provider, ClaudeCodeProvider)


# ---------------------------------------------------------------------------
# correlate_scans
# ---------------------------------------------------------------------------

class TestCorrelateScans:
    def test_no_signals_returns_empty(self):
        result, text = correlate_scans({})
        assert result["field_intake"] == {}
        assert "No signals" in result["analyst_notes"]
        assert text == ""

    def test_empty_scan_results(self):
        result, text = correlate_scans({"ch1": None, "ch2": {}})
        assert result["field_intake"] == {}

    def test_scan_with_no_signals_list(self):
        result, text = correlate_scans({"ch1": {"signals": "not a list"}})
        assert result["field_intake"] == {}

    def test_successful_correlation(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.analyst.PROJECT_ROOT", str(tmp_path))
        analysis_json = {
            "analysis_date": "2026-03-13",
            "total_raw_signals": 2,
            "deduplicated_signals": 1,
            "cross_channel_entities": [],
            "field_intake": {
                "tow_companies": [
                    {"entity": "Shady Tow", "signal_summary": "Overcharging", "confidence": 4, "severity": 3}
                ]
            },
            "immediate_alerts": [],
            "analyst_notes": "Quiet day.",
        }
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = (json.dumps(analysis_json), {"prompt_tokens": 100, "completion_tokens": 200})

        with mock.patch("wheat.analyst.get_analyst_provider", return_value=mock_provider):
            result, text = correlate_scans(
                {"ch1": {"channel_name": "BBB", "channel_type": "PUBLIC_RECORDS", "signals": [{"entity": "Shady Tow", "detail": "Overcharging"}]}}
            )

        assert "tow_companies" in result["field_intake"]
        assert result["analyst_notes"] == "Quiet day."
        # Check analysis file saved
        analysis_dir = tmp_path / "intake" / "analysis"
        assert analysis_dir.exists()
        files = list(analysis_dir.iterdir())
        assert len(files) == 1

    def test_json_parse_error_returns_raw(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.analyst.PROJECT_ROOT", str(tmp_path))
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = ("This is not JSON at all", {"prompt_tokens": 10, "completion_tokens": 10})

        with mock.patch("wheat.analyst.get_analyst_provider", return_value=mock_provider):
            result, text = correlate_scans(
                {"ch1": {"signals": [{"entity": "X"}]}}
            )

        assert result.get("parse_error") is True
        assert "This is not JSON" in result["analyst_notes"]

    def test_json_in_fenced_block(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.analyst.PROJECT_ROOT", str(tmp_path))
        analysis_json = {"field_intake": {}, "analyst_notes": "Clean."}
        fenced = f"```json\n{json.dumps(analysis_json)}\n```"
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = (fenced, {"prompt_tokens": 10, "completion_tokens": 10})

        with mock.patch("wheat.analyst.get_analyst_provider", return_value=mock_provider):
            result, text = correlate_scans({"ch1": {"signals": [{"x": 1}]}})

        assert result["analyst_notes"] == "Clean."

    def test_provider_exception(self):
        mock_provider = mock.MagicMock()
        mock_provider.generate.side_effect = Exception("Connection refused")

        with mock.patch("wheat.analyst.get_analyst_provider", return_value=mock_provider):
            result, text = correlate_scans({"ch1": {"signals": [{"x": 1}]}})

        assert "Connection refused" in result["analyst_notes"]
        assert text == ""

    def test_existing_cases_included(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.analyst.PROJECT_ROOT", str(tmp_path))
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = ('{"field_intake": {}, "analyst_notes": "ok"}', {"prompt_tokens": 10, "completion_tokens": 10})

        cases = [{"id": 1, "entity": "Bad Corp", "field": "tow_companies", "stage": "notice", "severity": 3}]
        with mock.patch("wheat.analyst.get_analyst_provider", return_value=mock_provider):
            correlate_scans({"ch1": {"signals": [{"x": 1}]}}, existing_cases=cases)

        prompt_used = mock_provider.generate.call_args[1]["prompt"]
        assert "Bad Corp" in prompt_used

    def test_immediate_alerts_printed(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr("wheat.analyst.PROJECT_ROOT", str(tmp_path))
        analysis = {"field_intake": {}, "immediate_alerts": ["Severe issue at dealer"], "analyst_notes": "alert"}
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = (json.dumps(analysis), {"prompt_tokens": 10, "completion_tokens": 10})

        with mock.patch("wheat.analyst.get_analyst_provider", return_value=mock_provider):
            correlate_scans({"ch1": {"signals": [{"x": 1}]}})

        captured = capsys.readouterr()
        assert "IMMEDIATE ALERT" in captured.out

    def test_counts_signals_across_channels(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.analyst.PROJECT_ROOT", str(tmp_path))
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = ('{"field_intake": {}, "analyst_notes": "ok"}', {"prompt_tokens": 10, "completion_tokens": 10})

        with mock.patch("wheat.analyst.get_analyst_provider", return_value=mock_provider):
            correlate_scans({
                "ch1": {"channel_name": "A", "signals": [{"a": 1}, {"b": 2}]},
                "ch2": {"channel_name": "B", "signals": [{"c": 3}]},
            })

        prompt = mock_provider.generate.call_args[1]["prompt"]
        assert "Signals (2)" in prompt
        assert "Signals (1)" in prompt


# ---------------------------------------------------------------------------
# build_field_guidance
# ---------------------------------------------------------------------------

class TestBuildFieldGuidance:
    def test_no_intake_returns_default(self):
        result = build_field_guidance("tow_companies", {"field_intake": {}})
        assert "no new signals" in result.lower()

    def test_missing_field_returns_default(self):
        result = build_field_guidance("emissions", {"field_intake": {"tow_companies": []}})
        assert "no new signals" in result.lower()

    def test_with_signals(self):
        analysis = {
            "field_intake": {
                "tow_companies": [
                    {
                        "entity": "Shady Tow LLC",
                        "signal_summary": "Overcharging for impound release",
                        "confidence": 4,
                        "severity": 3,
                        "law_cited": "CRS 42-4-2103",
                        "recommended_action": "Verify rate schedule",
                        "source_channels": ["bbb", "yelp"],
                    }
                ]
            },
            "cross_channel_entities": [],
            "analyst_notes": "Active pattern detected.",
        }
        result = build_field_guidance("tow_companies", analysis)
        assert "Shady Tow LLC" in result
        assert "Overcharging" in result
        assert "CRS 42-4-2103" in result
        assert "Verify rate schedule" in result
        assert "bbb, yelp" in result
        assert "Active pattern detected." in result

    def test_cross_channel_entities(self):
        analysis = {
            "field_intake": {"tow_companies": [{"entity": "X", "signal_summary": "Y"}]},
            "cross_channel_entities": [
                {"entity": "X Corp", "channels_seen": ["bbb", "yelp", "dora"], "recommended_fields": ["tow_companies"], "confidence": 5},
                {"entity": "Y Corp", "channels_seen": ["bbb"], "recommended_fields": ["auto_repair"], "confidence": 2},
            ],
        }
        result = build_field_guidance("tow_companies", analysis)
        assert "X Corp" in result
        assert "3 channels" in result
        assert "Y Corp" not in result  # Not recommended for tow_companies

    def test_multiple_signals(self):
        analysis = {
            "field_intake": {
                "auto_repair": [
                    {"entity": "A", "signal_summary": "Issue 1"},
                    {"entity": "B", "signal_summary": "Issue 2"},
                ]
            },
        }
        result = build_field_guidance("auto_repair", analysis)
        assert "2 signal(s)" in result
        assert "A" in result
        assert "B" in result


# ---------------------------------------------------------------------------
# synthesize_briefing
# ---------------------------------------------------------------------------

class TestSynthesizeBriefing:
    def test_default_no_data(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.analyst.PROJECT_ROOT", str(tmp_path))
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = ("# BRIEFING\nQuiet day.", {"prompt_tokens": 50, "completion_tokens": 100})

        with mock.patch("wheat.analyst.get_analyst_provider", return_value=mock_provider):
            text, path = synthesize_briefing()

        assert "BRIEFING" in text
        assert os.path.exists(path)
        assert path.endswith(".md")
        # JSON companion file also saved
        json_path = path.replace(".md", ".json")
        assert os.path.exists(json_path)

    def test_with_scan_results(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.analyst.PROJECT_ROOT", str(tmp_path))
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = ("Briefing text", {"prompt_tokens": 50, "completion_tokens": 100})

        scans = {"ch1": {"signals": [{"a": 1}]}, "ch2": None}
        with mock.patch("wheat.analyst.get_analyst_provider", return_value=mock_provider):
            synthesize_briefing(scan_results=scans)

        prompt = mock_provider.generate.call_args[1]["prompt"]
        assert "Scanned 1 channels" in prompt
        assert "1 raw signals" in prompt

    def test_with_field_results(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.analyst.PROJECT_ROOT", str(tmp_path))
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = ("Briefing", {"prompt_tokens": 50, "completion_tokens": 100})

        fields = {
            "tow_companies": {
                "seeds": [
                    {"status": "Fruitful", "output": ["found issue"]},
                    {"status": "Barren", "output": []},
                ]
            }
        }
        with mock.patch("wheat.analyst.get_analyst_provider", return_value=mock_provider):
            synthesize_briefing(field_results=fields)

        prompt = mock_provider.generate.call_args[1]["prompt"]
        assert "tow_companies" in prompt
        assert "1 fruitful" in prompt

    def test_with_cross_field_entities(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.analyst.PROJECT_ROOT", str(tmp_path))
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = ("Briefing", {"prompt_tokens": 50, "completion_tokens": 100})

        cross = [{"entity": "Bad Corp", "field_count": 3, "fields": ["tow", "repair", "dealer"], "max_severity": 4}]
        with mock.patch("wheat.analyst.get_analyst_provider", return_value=mock_provider):
            synthesize_briefing(cross_field_entities=cross)

        prompt = mock_provider.generate.call_args[1]["prompt"]
        assert "Bad Corp" in prompt
        assert "3 fields" in prompt

    def test_provider_error_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.analyst.PROJECT_ROOT", str(tmp_path))
        mock_provider = mock.MagicMock()
        mock_provider.generate.side_effect = Exception("LLM down")

        with mock.patch("wheat.analyst.get_analyst_provider", return_value=mock_provider):
            text, path = synthesize_briefing()

        assert "BRIEFING" in text
        assert "LLM down" in text
        assert path.endswith("_fallback.txt")
        assert os.path.exists(path)

    def test_community_reports_included(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.analyst.PROJECT_ROOT", str(tmp_path))
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = ("Briefing", {"prompt_tokens": 50, "completion_tokens": 100})

        # Create a community report for today
        intake_dir = tmp_path / "intake"
        intake_dir.mkdir()
        today = date.today().isoformat().replace("-", "")
        report = {"entity": "Bad Dealer", "category": "used_car_dealers", "severity": 4, "location": "Englewood", "description": "Selling flood-damaged vehicles"}
        (intake_dir / f"report_{today}_001.json").write_text(json.dumps(report))

        with mock.patch("wheat.analyst.get_analyst_provider", return_value=mock_provider):
            synthesize_briefing()

        prompt = mock_provider.generate.call_args[1]["prompt"]
        assert "Bad Dealer" in prompt
        assert "1 report(s)" in prompt

    def test_saves_json_companion(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wheat.analyst.PROJECT_ROOT", str(tmp_path))
        mock_provider = mock.MagicMock()
        mock_provider.generate.return_value = ("Briefing", {"prompt_tokens": 50, "completion_tokens": 100})

        with mock.patch("wheat.analyst.get_analyst_provider", return_value=mock_provider):
            text, md_path = synthesize_briefing()

        json_path = md_path.replace(".md", ".json")
        with open(json_path) as f:
            data = json.load(f)
        assert "date" in data
        assert "generated_at" in data
        assert data["provider"] == "analyst_brain"


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

class TestPromptTemplates:
    def test_correlation_prompt_has_placeholders(self):
        assert "{scan_data}" in CORRELATION_PROMPT
        assert "{existing_cases}" in CORRELATION_PROMPT
        assert "{run_date}" in CORRELATION_PROMPT

    def test_briefing_prompt_has_placeholders(self):
        assert "{run_date}" in BRIEFING_PROMPT
        assert "{scan_summary}" in BRIEFING_PROMPT
        assert "{field_results}" in BRIEFING_PROMPT
        assert "{escalation_report}" in BRIEFING_PROMPT
        assert "{cross_field}" in BRIEFING_PROMPT
