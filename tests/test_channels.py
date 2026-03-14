"""Tests for wheat/channels.py — channel loading, routing, intake processing."""

import json
import os
import pytest
from unittest import mock

import wheat.channels as channels_mod
from wheat.channels import (
    load_channels,
    save_channels,
    get_default_channels,
    get_channels_for_field,
    get_fields_for_channel,
    process_intake,
    channel_status_report,
)


@pytest.fixture(autouse=True)
def _isolate_paths(tmp_path, monkeypatch):
    """Redirect all file I/O to tmp_path so tests never touch real project files."""
    monkeypatch.setattr(channels_mod, "CHANNELS_PATH", str(tmp_path / "channels.json"))
    monkeypatch.setattr(channels_mod, "INTAKE_DIR", str(tmp_path / "intake"))


# ── get_default_channels ─────────────────────────────────────

class TestGetDefaultChannels:
    def test_returns_dict(self):
        ch = get_default_channels()
        assert isinstance(ch, dict)
        assert len(ch) > 0

    def test_all_channels_have_required_keys(self):
        required = {"name", "channel_type", "sources", "fields", "frequency", "description"}
        for cid, cdata in get_default_channels().items():
            missing = required - set(cdata.keys())
            assert not missing, f"{cid} missing keys: {missing}"

    def test_known_channel_types(self):
        valid_types = {"REVIEWS", "REGULATORY", "PUBLIC_RECORDS", "NEWS", "COMMUNITY", "SOCIAL", "COURT", "API"}
        for cid, cdata in get_default_channels().items():
            assert cdata["channel_type"] in valid_types, f"{cid} has unknown type {cdata['channel_type']}"

    def test_community_intake_exists(self):
        ch = get_default_channels()
        assert "community_intake" in ch
        assert ch["community_intake"]["channel_type"] == "COMMUNITY"
        assert ch["community_intake"]["frequency"] == "realtime"

    def test_wildcard_fields(self):
        """Some channels use 'all' wildcard in fields list."""
        ch = get_default_channels()
        wildcard = [cid for cid, c in ch.items() if "all" in c["fields"]]
        assert len(wildcard) >= 1  # at least community_intake, local_news_rss, nextdoor_social


# ── load_channels / save_channels ────────────────────────────

class TestLoadSaveChannels:
    def test_load_falls_back_to_defaults_when_no_file(self):
        ch = load_channels()
        assert ch == get_default_channels()

    def test_save_then_load_roundtrips(self, tmp_path):
        data = {"test_channel": {"name": "Test", "channel_type": "NEWS",
                                  "sources": ["s1"], "fields": ["f1"],
                                  "frequency": "daily", "description": "desc"}}
        save_channels(data)
        loaded = load_channels()
        assert loaded == data

    def test_save_creates_json_file(self, tmp_path):
        save_channels({"ch": {"name": "X"}})
        path = str(tmp_path / "channels.json")
        assert os.path.exists(path)
        with open(path) as f:
            content = json.load(f)
        assert "ch" in content

    def test_load_reads_custom_file_over_defaults(self, tmp_path):
        custom = {"only_one": {"name": "Custom Channel"}}
        path = str(tmp_path / "channels.json")
        with open(path, "w") as f:
            json.dump(custom, f)
        loaded = load_channels()
        assert loaded == custom
        assert "google_reviews_auto" not in loaded


# ── get_channels_for_field ───────────────────────────────────

class TestGetChannelsForField:
    def test_specific_field_match(self, tmp_path):
        save_channels({
            "ch_a": {"name": "A", "fields": ["fleet_compliance"]},
            "ch_b": {"name": "B", "fields": ["tow_companies"]},
        })
        result = get_channels_for_field("fleet_compliance")
        assert "ch_a" in result
        assert "ch_b" not in result

    def test_wildcard_all_matches_any_field(self, tmp_path):
        save_channels({
            "ch_all": {"name": "All", "fields": ["all"]},
            "ch_spec": {"name": "Spec", "fields": ["tow_companies"]},
        })
        result = get_channels_for_field("anything_here")
        assert "ch_all" in result
        assert "ch_spec" not in result

    def test_multiple_channels_for_one_field(self, tmp_path):
        save_channels({
            "ch_a": {"name": "A", "fields": ["fleet_compliance", "tow_companies"]},
            "ch_b": {"name": "B", "fields": ["fleet_compliance"]},
            "ch_c": {"name": "C", "fields": ["auto_repair"]},
        })
        result = get_channels_for_field("fleet_compliance")
        assert len(result) == 2
        assert "ch_a" in result
        assert "ch_b" in result

    def test_no_match_returns_empty(self, tmp_path):
        save_channels({"ch": {"name": "X", "fields": ["auto_repair"]}})
        result = get_channels_for_field("nonexistent_field")
        assert result == {}

    def test_missing_fields_key_handled(self, tmp_path):
        save_channels({"ch": {"name": "No fields"}})
        result = get_channels_for_field("anything")
        assert result == {}


# ── get_fields_for_channel ───────────────────────────────────

class TestGetFieldsForChannel:
    def test_specific_fields_returned(self, tmp_path):
        save_channels({
            "ch_a": {"name": "A", "fields": ["fleet_compliance", "tow_companies"]},
        })
        result = get_fields_for_channel("ch_a")
        assert result == ["fleet_compliance", "tow_companies"]

    def test_unknown_channel_returns_empty(self, tmp_path):
        save_channels({"ch_a": {"name": "A", "fields": ["x"]}})
        result = get_fields_for_channel("nonexistent")
        assert result == []

    def test_all_wildcard_loads_project_keys(self, tmp_path):
        save_channels({"ch_all": {"name": "All", "fields": ["all"]}})
        mock_projects = {"field_a": {}, "field_b": {}, "field_c": {}}
        with mock.patch("wheat.channels.load_projects", create=True, return_value=mock_projects) as mp:
            # The import is dynamic inside the function
            with mock.patch.dict("sys.modules", {"wheat.paths": mock.MagicMock(load_projects=lambda: mock_projects)}):
                from wheat import channels as ch
                # Patch at import site
                with mock.patch("wheat.paths.load_projects", return_value=mock_projects):
                    result = get_fields_for_channel("ch_all")
        assert set(result) == {"field_a", "field_b", "field_c"}

    def test_no_fields_key_returns_empty(self, tmp_path):
        save_channels({"ch": {"name": "No fields"}})
        result = get_fields_for_channel("ch")
        assert result == []


# ── process_intake ───────────────────────────────────────────

class TestProcessIntake:
    @pytest.fixture(autouse=True)
    def _mock_escalation(self, monkeypatch):
        """Mock escalation DB so process_intake doesn't need real SQLite."""
        monkeypatch.setattr(channels_mod, "init_escalation_db", lambda: None)
        self._case_counter = 0

        def fake_create_case(**kwargs):
            self._case_counter += 1
            return self._case_counter

        monkeypatch.setattr(channels_mod, "create_case", fake_create_case)

    def test_creates_report_file(self, tmp_path):
        result = process_intake({"category": "tow_company", "entity": "Bad Tow Co",
                                  "description": "Predatory towing"})
        assert os.path.exists(result["report_file"])
        with open(result["report_file"]) as f:
            saved = json.load(f)
        assert saved["entity"] == "Bad Tow Co"
        assert saved["status"] == "pending"
        assert "received_at" in saved

    def test_routes_to_correct_field(self):
        mappings = {
            "dangerous_driving": "fleet_compliance",
            "tow_company": "tow_companies",
            "used_car_dealer": "used_car_dealers",
            "auto_repair": "auto_repair",
            "noise_exhaust": "exhaust_noise",
            "school_zone": "school_zone_safety",
            "pedestrian_cyclist": "pedestrian_cyclist",
            "parking_booting": "parking_booting",
            "window_tint": "window_tint",
            "registration_plates": "title_registration",
            "emissions": "emissions_environmental",
            "intersection_road": "road_intersection_safety",
            "insurance": "auto_insurance",
            "dealer_financing": "dealer_financing",
            "rideshare_delivery": "rideshare_delivery",
        }
        for category, expected_field in mappings.items():
            result = process_intake({"category": category, "entity": "Test",
                                      "description": "test"})
            assert result["target_field"] == expected_field, f"{category} -> {result['target_field']}, expected {expected_field}"

    def test_unknown_category_defaults_to_fleet_compliance(self):
        result = process_intake({"category": "alien_invasion", "entity": "X",
                                  "description": "test"})
        assert result["target_field"] == "fleet_compliance"

    def test_missing_category_defaults_to_fleet_compliance(self):
        result = process_intake({"entity": "Y", "description": "no category"})
        assert result["target_field"] == "fleet_compliance"

    def test_returns_case_id(self):
        result = process_intake({"category": "tow_company", "entity": "Tow Co",
                                  "description": "Predatory"})
        assert "case_id" in result
        assert isinstance(result["case_id"], int)

    def test_location_prepended_to_issue(self, monkeypatch):
        calls = []

        def capture_create_case(**kwargs):
            calls.append(kwargs)
            return 1

        monkeypatch.setattr(channels_mod, "create_case", capture_create_case)
        process_intake({"category": "auto_repair", "entity": "Shop",
                        "description": "Overcharged", "location": "123 Main St"})
        assert calls[0]["issue"] == "[123 Main St] Overcharged"

    def test_no_location_uses_description_only(self, monkeypatch):
        calls = []

        def capture_create_case(**kwargs):
            calls.append(kwargs)
            return 1

        monkeypatch.setattr(channels_mod, "create_case", capture_create_case)
        process_intake({"category": "auto_repair", "entity": "Shop",
                        "description": "Overcharged"})
        assert calls[0]["issue"] == "Overcharged"

    def test_severity_parsed_as_int(self, monkeypatch):
        calls = []

        def capture_create_case(**kwargs):
            calls.append(kwargs)
            return 1

        monkeypatch.setattr(channels_mod, "create_case", capture_create_case)
        process_intake({"category": "emissions", "entity": "Smoky",
                        "description": "Black smoke", "severity": "7"})
        assert calls[0]["severity"] == 7

    def test_default_severity_is_one(self, monkeypatch):
        calls = []

        def capture_create_case(**kwargs):
            calls.append(kwargs)
            return 1

        monkeypatch.setattr(channels_mod, "create_case", capture_create_case)
        process_intake({"category": "emissions", "entity": "X", "description": "d"})
        assert calls[0]["severity"] == 1

    def test_empty_entity_becomes_unknown(self, monkeypatch):
        calls = []

        def capture_create_case(**kwargs):
            calls.append(kwargs)
            return 1

        monkeypatch.setattr(channels_mod, "create_case", capture_create_case)
        process_intake({"category": "tow_company", "entity": "  ", "description": "d"})
        assert calls[0]["entity"] == "Unknown Entity"

    def test_missing_entity_becomes_unknown(self, monkeypatch):
        calls = []

        def capture_create_case(**kwargs):
            calls.append(kwargs)
            return 1

        monkeypatch.setattr(channels_mod, "create_case", capture_create_case)
        process_intake({"category": "tow_company", "description": "d"})
        assert calls[0]["entity"] == "Unknown Entity"

    def test_intake_dir_created(self, tmp_path):
        intake_dir = str(tmp_path / "intake")
        assert not os.path.exists(intake_dir)
        process_intake({"category": "tow_company", "entity": "X", "description": "d"})
        assert os.path.isdir(intake_dir)

    def test_case_source_is_community_intake(self, monkeypatch):
        calls = []

        def capture_create_case(**kwargs):
            calls.append(kwargs)
            return 1

        monkeypatch.setattr(channels_mod, "create_case", capture_create_case)
        process_intake({"category": "auto_repair", "entity": "X", "description": "d"})
        assert calls[0]["source"] == "community_intake"


# ── channel_status_report ────────────────────────────────────

class TestChannelStatusReport:
    def test_returns_string(self, tmp_path):
        save_channels(get_default_channels())
        report = channel_status_report()
        assert isinstance(report, str)
        assert len(report) > 0

    def test_includes_channel_names(self, tmp_path):
        save_channels({
            "ch_test": {"name": "Test Channel", "channel_type": "NEWS",
                        "sources": ["s1", "s2"], "fields": ["f1"],
                        "frequency": "daily"},
        })
        report = channel_status_report()
        assert "Test Channel" in report
        assert "NEWS" in report
        assert "daily" in report

    def test_shows_source_count(self, tmp_path):
        save_channels({
            "ch": {"name": "Multi", "channel_type": "API",
                   "sources": ["a", "b", "c"], "fields": ["x"],
                   "frequency": "weekly"},
        })
        report = channel_status_report()
        assert "3" in report  # 3 sources

    def test_shows_fields(self, tmp_path):
        save_channels({
            "ch": {"name": "X", "channel_type": "API",
                   "sources": ["s"], "fields": ["fleet_compliance", "tow_companies"],
                   "frequency": "daily"},
        })
        report = channel_status_report()
        assert "fleet_compliance" in report
        assert "tow_companies" in report

    def test_empty_channels(self, tmp_path):
        save_channels({})
        report = channel_status_report()
        assert report == ""
