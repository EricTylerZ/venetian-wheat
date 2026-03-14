"""Tests for wheat/manual_scan.py — manual copy-paste scan interface."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import wheat.manual_scan as ms


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def temp_dirs(tmp_path, monkeypatch):
    """Redirect intake/manual_scans to temp directory."""
    intake = tmp_path / "intake"
    manual = intake / "manual_scans"
    monkeypatch.setattr(ms, "INTAKE_DIR", str(intake))
    monkeypatch.setattr(ms, "MANUAL_DIR", str(manual))
    return {"intake": intake, "manual": manual}


MOCK_CHANNELS = {
    "google_reviews_auto": {
        "name": "Google Reviews - Auto Dealers",
        "channel_type": "REVIEWS",
        "sources": ["Google Maps auto dealer reviews", "Yelp auto dealers"],
        "fields": ["auto_dealers"],
    },
    "court_records": {
        "name": "Court Records",
        "channel_type": "COURT",
        "sources": ["Arapahoe County court filings"],
        "fields": ["litigation"],
    },
}

MOCK_PROJECTS = {
    "auto_dealers": {
        "name": "Auto Dealer Accountability",
        "description": "Track deceptive practices at auto dealerships",
        "jurisdiction": "Arapahoe County, CO",
        "laws": ["CRS 6-1-105 (Deceptive Trade Practices)", "TILA"],
    },
    "fleet_compliance": {
        "name": "Fleet Compliance",
        "description": "Monitor fleet safety and emissions",
    },
}

MOCK_PROJECT_CONFIG = {
    "name": "Auto Dealer Accountability",
    "description": "Track deceptive practices",
}


def _mock_get_channels_for_field(field_id):
    return {
        cid: cdata for cid, cdata in MOCK_CHANNELS.items()
        if field_id in cdata.get("fields", [])
    }


# ---------------------------------------------------------------------------
# get_channel_prompt
# ---------------------------------------------------------------------------

class TestGetChannelPrompt:
    @patch.object(ms, "load_channels", return_value=MOCK_CHANNELS)
    def test_returns_prompt_for_valid_channel(self, mock_ch):
        prompt = ms.get_channel_prompt("google_reviews_auto")
        assert prompt is not None
        assert "Google Maps auto dealer reviews" in prompt
        assert "Yelp auto dealers" in prompt

    @patch.object(ms, "load_channels", return_value=MOCK_CHANNELS)
    def test_uses_channel_type_template(self, mock_ch):
        prompt = ms.get_channel_prompt("google_reviews_auto")
        assert prompt is not None
        # REVIEWS template should be used, not NEWS

    @patch.object(ms, "load_channels", return_value=MOCK_CHANNELS)
    def test_returns_none_for_unknown_channel(self, mock_ch):
        prompt = ms.get_channel_prompt("nonexistent")
        assert prompt is None

    @patch.object(ms, "load_channels", return_value={
        "simple": {"name": "Simple", "channel_type": "UNKNOWN_TYPE", "sources": ["src1"]},
    })
    def test_falls_back_to_news_template(self, mock_ch):
        prompt = ms.get_channel_prompt("simple")
        assert prompt is not None
        assert "src1" in prompt

    @patch.object(ms, "load_channels", return_value={
        "nosrc": {"name": "NoSrc", "channel_type": "NEWS"},
    })
    def test_handles_no_sources(self, mock_ch):
        prompt = ms.get_channel_prompt("nosrc")
        assert prompt is not None


# ---------------------------------------------------------------------------
# get_field_prompt
# ---------------------------------------------------------------------------

class TestGetFieldPrompt:
    @patch.object(ms, "get_channels_for_field", side_effect=_mock_get_channels_for_field)
    @patch.object(ms, "load_projects", return_value=MOCK_PROJECTS)
    def test_returns_prompt_for_valid_field(self, mock_proj, mock_ch):
        prompt = ms.get_field_prompt("auto_dealers")
        assert prompt is not None
        assert "Auto Dealer Accountability" in prompt
        assert "deceptive practices" in prompt.lower()

    @patch.object(ms, "get_channels_for_field", side_effect=_mock_get_channels_for_field)
    @patch.object(ms, "load_projects", return_value=MOCK_PROJECTS)
    def test_includes_jurisdiction(self, mock_proj, mock_ch):
        prompt = ms.get_field_prompt("auto_dealers")
        assert "Arapahoe County, CO" in prompt

    @patch.object(ms, "get_channels_for_field", side_effect=_mock_get_channels_for_field)
    @patch.object(ms, "load_projects", return_value=MOCK_PROJECTS)
    def test_includes_laws(self, mock_proj, mock_ch):
        prompt = ms.get_field_prompt("auto_dealers")
        assert "CRS 6-1-105" in prompt
        assert "TILA" in prompt

    @patch.object(ms, "get_channels_for_field", side_effect=_mock_get_channels_for_field)
    @patch.object(ms, "load_projects", return_value=MOCK_PROJECTS)
    def test_includes_channel_sources(self, mock_proj, mock_ch):
        prompt = ms.get_field_prompt("auto_dealers")
        assert "Google Maps auto dealer reviews" in prompt

    @patch.object(ms, "get_channels_for_field", return_value={})
    @patch.object(ms, "load_projects", return_value=MOCK_PROJECTS)
    def test_field_with_no_channels(self, mock_proj, mock_ch):
        prompt = ms.get_field_prompt("fleet_compliance")
        assert prompt is not None
        assert "Fleet Compliance" in prompt

    @patch.object(ms, "load_projects", return_value=MOCK_PROJECTS)
    def test_returns_none_for_unknown_field(self, mock_proj):
        prompt = ms.get_field_prompt("nonexistent")
        assert prompt is None

    @patch.object(ms, "get_channels_for_field", return_value={})
    @patch.object(ms, "load_projects", return_value=MOCK_PROJECTS)
    def test_includes_json_format_instructions(self, mock_proj, mock_ch):
        prompt = ms.get_field_prompt("auto_dealers")
        assert "JSON" in prompt
        assert "entity" in prompt
        assert "severity" in prompt

    @patch.object(ms, "get_channels_for_field", return_value={})
    @patch.object(ms, "load_projects", return_value={
        "minimal": {"name": "Minimal Field"},
    })
    def test_field_without_laws(self, mock_proj, mock_ch):
        prompt = ms.get_field_prompt("minimal")
        assert prompt is not None
        assert "Applicable laws" not in prompt


# ---------------------------------------------------------------------------
# save_manual_response
# ---------------------------------------------------------------------------

class TestSaveManualResponse:
    def test_saves_valid_json_signals(self, temp_dirs):
        signals = [
            {"entity": "Bad Dealer", "issue": "Odometer fraud", "severity": 4},
            {"entity": "Shady Lender", "issue": "Hidden fees", "severity": 2},
        ]
        path = ms.save_manual_response("auto_dealers", json.dumps(signals))
        assert os.path.exists(path)
        with open(path) as f:
            result = json.load(f)
        assert result["source"] == "auto_dealers"
        assert result["method"] == "manual_copy_paste"
        assert len(result["signals"]) == 2
        assert result["signals"][0]["entity"] == "Bad Dealer"

    def test_creates_manual_dir(self, temp_dirs):
        assert not temp_dirs["manual"].exists()
        ms.save_manual_response("test", "[]")
        assert temp_dirs["manual"].exists()

    def test_saves_empty_array(self, temp_dirs):
        path = ms.save_manual_response("test", "[]")
        with open(path) as f:
            result = json.load(f)
        assert result["signals"] == []

    def test_strips_json_code_block(self, temp_dirs):
        response = '```json\n[{"entity": "Corp", "severity": 3}]\n```'
        path = ms.save_manual_response("test", response)
        with open(path) as f:
            result = json.load(f)
        assert len(result["signals"]) == 1
        assert result["signals"][0]["entity"] == "Corp"

    def test_strips_generic_code_block(self, temp_dirs):
        response = '```\n[{"entity": "Corp"}]\n```'
        path = ms.save_manual_response("test", response)
        with open(path) as f:
            result = json.load(f)
        assert len(result["signals"]) == 1

    def test_handles_unparseable_response(self, temp_dirs):
        path = ms.save_manual_response("test", "This is not JSON at all")
        with open(path) as f:
            result = json.load(f)
        assert len(result["signals"]) == 1
        assert result["signals"][0]["parse_error"] is True
        assert "This is not JSON at all" in result["signals"][0]["raw_response"]

    def test_filename_includes_source_and_timestamp(self, temp_dirs):
        path = ms.save_manual_response("fleet_compliance", "[]")
        filename = os.path.basename(path)
        assert filename.startswith("fleet_compliance_")
        assert filename.endswith(".json")

    def test_includes_scanned_at_timestamp(self, temp_dirs):
        path = ms.save_manual_response("test", "[]")
        with open(path) as f:
            result = json.load(f)
        assert "scanned_at" in result
        # Should be parseable as ISO datetime
        datetime.fromisoformat(result["scanned_at"])

    def test_single_signal_object(self, temp_dirs):
        # A single object (not array) is valid JSON but not a list
        response = '{"entity": "Solo", "severity": 1}'
        path = ms.save_manual_response("test", response)
        with open(path) as f:
            result = json.load(f)
        # single object is valid json, signals should be the parsed dict
        assert result["signals"]["entity"] == "Solo"

    def test_nested_code_blocks(self, temp_dirs):
        response = 'Here is the data:\n```json\n[{"entity": "X"}]\n```\nDone.'
        path = ms.save_manual_response("test", response)
        with open(path) as f:
            result = json.load(f)
        assert result["signals"][0]["entity"] == "X"


# ---------------------------------------------------------------------------
# interactive_mode (mocked input/output)
# ---------------------------------------------------------------------------

class TestInteractiveMode:
    @patch("builtins.input", side_effect=["q"])
    @patch.object(ms, "load_projects", return_value=MOCK_PROJECTS)
    def test_quit_immediately(self, mock_proj, mock_input):
        ms.interactive_mode()  # should not raise

    @patch("builtins.input", side_effect=["invalid", "q"])
    @patch.object(ms, "load_projects", return_value=MOCK_PROJECTS)
    def test_invalid_choice(self, mock_proj, mock_input):
        ms.interactive_mode()  # should not raise

    @patch("builtins.input", side_effect=[
        "1",  # pick first field
        '[]',  # paste empty response
        "END",  # end marker
        "n",  # don't scan another
    ])
    @patch.object(ms, "get_channels_for_field", return_value={})
    @patch.object(ms, "load_projects", return_value=MOCK_PROJECTS)
    def test_select_field_and_paste(self, mock_proj, mock_ch, mock_input, temp_dirs):
        ms.interactive_mode()
        # Should have saved a file
        assert temp_dirs["manual"].exists()
        files = list(temp_dirs["manual"].iterdir())
        assert len(files) == 1

    @patch("builtins.input", side_effect=[
        "1",  # pick first field
        "",  # empty response
        "END",
        "n",
    ])
    @patch.object(ms, "get_channels_for_field", return_value={})
    @patch.object(ms, "load_projects", return_value=MOCK_PROJECTS)
    def test_empty_paste_does_not_save(self, mock_proj, mock_ch, mock_input, temp_dirs):
        ms.interactive_mode()
        if temp_dirs["manual"].exists():
            assert list(temp_dirs["manual"].iterdir()) == []
