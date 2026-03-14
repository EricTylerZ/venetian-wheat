"""Tests for wheat/daily_intake.py — batch intake processing pipeline."""

import json
import os
import pytest
from unittest import mock

import wheat.daily_intake as intake_mod
from wheat.daily_intake import (
    validate_report,
    get_pending_reports,
    process_pending_reports,
    get_unprocessed_scans,
    process_scan_results,
    intake_summary,
    run_daily_intake,
    CATEGORY_TO_FIELD,
    REQUIRED_REPORT_FIELDS,
)


@pytest.fixture(autouse=True)
def _isolate_paths(tmp_path, monkeypatch):
    """Redirect all I/O to tmp_path."""
    intake_dir = str(tmp_path / "intake")
    scans_dir = str(tmp_path / "intake" / "scans")
    monkeypatch.setattr(intake_mod, "INTAKE_DIR", intake_dir)
    monkeypatch.setattr(intake_mod, "SCANS_DIR", scans_dir)


def _write_report(tmp_path, filename, data):
    """Helper to write a report JSON file."""
    intake_dir = tmp_path / "intake"
    intake_dir.mkdir(exist_ok=True)
    filepath = intake_dir / filename
    filepath.write_text(json.dumps(data))
    return str(filepath)


def _write_scan(tmp_path, filename, data):
    """Helper to write a scan result file."""
    scans_dir = tmp_path / "intake" / "scans"
    scans_dir.mkdir(parents=True, exist_ok=True)
    filepath = scans_dir / filename
    filepath.write_text(json.dumps(data))
    return str(filepath)


# ── validate_report ──────────────────────────────────────────

class TestValidateReport:
    def test_valid_report(self):
        report = {"category": "tow_company", "entity": "Bad Tow Co",
                  "description": "Predatory towing"}
        valid, errors = validate_report(report)
        assert valid is True
        assert errors == []

    def test_missing_required_fields(self):
        report = {"category": "tow_company"}
        valid, errors = validate_report(report)
        assert valid is False
        assert any("Missing required" in e for e in errors)

    def test_empty_entity(self):
        report = {"category": "tow_company", "entity": "  ",
                  "description": "Something"}
        valid, errors = validate_report(report)
        assert valid is False
        assert any("Entity" in e for e in errors)

    def test_empty_description(self):
        report = {"category": "tow_company", "entity": "X",
                  "description": "  "}
        valid, errors = validate_report(report)
        assert valid is False
        assert any("Description" in e for e in errors)

    def test_unknown_category(self):
        report = {"category": "alien_invasion", "entity": "X",
                  "description": "Something"}
        valid, errors = validate_report(report)
        assert valid is False
        assert any("Unknown category" in e for e in errors)

    def test_valid_severity(self):
        report = {"category": "tow_company", "entity": "X",
                  "description": "d", "severity": 5}
        valid, errors = validate_report(report)
        assert valid is True

    def test_severity_out_of_range(self):
        report = {"category": "tow_company", "entity": "X",
                  "description": "d", "severity": 11}
        valid, errors = validate_report(report)
        assert valid is False
        assert any("1-10" in e for e in errors)

    def test_severity_not_integer(self):
        report = {"category": "tow_company", "entity": "X",
                  "description": "d", "severity": "high"}
        valid, errors = validate_report(report)
        assert valid is False
        assert any("integer" in e for e in errors)

    def test_no_severity_is_ok(self):
        report = {"category": "tow_company", "entity": "X",
                  "description": "d"}
        valid, _ = validate_report(report)
        assert valid is True

    def test_all_categories_valid(self):
        for cat in CATEGORY_TO_FIELD:
            report = {"category": cat, "entity": "X", "description": "d"}
            valid, _ = validate_report(report)
            assert valid is True, f"Category {cat} should be valid"


# ── get_pending_reports ──────────────────────────────────────

class TestGetPendingReports:
    def test_no_intake_dir(self):
        assert get_pending_reports() == []

    def test_finds_pending_reports(self, tmp_path):
        _write_report(tmp_path, "report_20260312_100000.json",
                      {"status": "pending", "entity": "X"})
        _write_report(tmp_path, "report_20260312_100001.json",
                      {"status": "processed", "entity": "Y"})
        pending = get_pending_reports()
        assert len(pending) == 1
        assert pending[0][1]["entity"] == "X"

    def test_ignores_non_report_files(self, tmp_path):
        _write_report(tmp_path, "notes.json", {"status": "pending"})
        _write_report(tmp_path, "report_20260312.json",
                      {"status": "pending", "entity": "X"})
        pending = get_pending_reports()
        assert len(pending) == 1

    def test_sorted_by_filename(self, tmp_path):
        _write_report(tmp_path, "report_20260312_120000.json",
                      {"status": "pending", "entity": "B"})
        _write_report(tmp_path, "report_20260312_100000.json",
                      {"status": "pending", "entity": "A"})
        pending = get_pending_reports()
        assert pending[0][1]["entity"] == "A"
        assert pending[1][1]["entity"] == "B"

    def test_skips_corrupt_json(self, tmp_path):
        intake_dir = tmp_path / "intake"
        intake_dir.mkdir(exist_ok=True)
        (intake_dir / "report_20260312_100000.json").write_text("not json{{{")
        _write_report(tmp_path, "report_20260312_100001.json",
                      {"status": "pending", "entity": "Good"})
        pending = get_pending_reports()
        assert len(pending) == 1


# ── process_pending_reports ──────────────────────────────────

class TestProcessPendingReports:
    @pytest.fixture(autouse=True)
    def _mock_escalation(self, monkeypatch):
        self._case_counter = 0

        def fake_create_case(**kwargs):
            self._case_counter += 1
            return self._case_counter

        monkeypatch.setattr(intake_mod, "init_escalation_db", lambda: None)
        monkeypatch.setattr(intake_mod, "create_case", fake_create_case)

    def test_no_pending(self):
        results = process_pending_reports()
        assert results["processed"] == 0
        assert results["invalid"] == 0

    def test_processes_valid_report(self, tmp_path):
        _write_report(tmp_path, "report_20260312_100000.json", {
            "status": "pending", "category": "tow_company",
            "entity": "Bad Tow", "description": "Predatory towing",
        })
        results = process_pending_reports()
        assert results["processed"] == 1
        assert len(results["cases_created"]) == 1
        assert results["cases_created"][0]["field"] == "tow_companies"

    def test_marks_invalid_report(self, tmp_path):
        _write_report(tmp_path, "report_20260312_100000.json", {
            "status": "pending", "category": "tow_company",
            "entity": "", "description": "",
        })
        results = process_pending_reports()
        assert results["invalid"] == 1
        assert len(results["errors"]) == 1

        # Check file was updated
        data = json.loads((tmp_path / "intake" / "report_20260312_100000.json").read_text())
        assert data["status"] == "invalid"
        assert "validation_errors" in data

    def test_skips_already_processed(self, tmp_path):
        _write_report(tmp_path, "report_20260312_100000.json", {
            "status": "pending", "case_id": 42,
            "category": "tow_company", "entity": "X", "description": "d",
        })
        results = process_pending_reports()
        assert results["skipped"] == 1
        assert results["processed"] == 0

    def test_updates_report_file(self, tmp_path):
        _write_report(tmp_path, "report_20260312_100000.json", {
            "status": "pending", "category": "auto_repair",
            "entity": "Shady Shop", "description": "Overcharged", "severity": 3,
        })
        process_pending_reports()

        data = json.loads((tmp_path / "intake" / "report_20260312_100000.json").read_text())
        assert data["status"] == "processed"
        assert data["case_id"] == 1
        assert data["target_field"] == "auto_repair"
        assert "processed_at" in data

    def test_location_in_case_issue(self, tmp_path, monkeypatch):
        calls = []

        def capture_create(**kwargs):
            calls.append(kwargs)
            return 1

        monkeypatch.setattr(intake_mod, "create_case", capture_create)
        _write_report(tmp_path, "report_20260312_100000.json", {
            "status": "pending", "category": "tow_company",
            "entity": "Tow Co", "description": "Bad", "location": "123 Main",
        })
        process_pending_reports()
        assert calls[0]["issue"] == "[123 Main] Bad"

    def test_default_field_for_missing_category(self, tmp_path):
        _write_report(tmp_path, "report_20260312_100000.json", {
            "status": "pending", "category": "",
            "entity": "Unknown Biz", "description": "Something happened",
        })
        results = process_pending_reports()
        # Empty category is not in CATEGORY_TO_FIELD, but validate allows empty
        # Actually empty category will fail validation since it's not in the map
        # Let me check: validate_report only checks unknown if category is truthy
        # So empty string passes validation, routes to default fleet_compliance
        assert results["processed"] == 1
        assert results["cases_created"][0]["field"] == "fleet_compliance"

    def test_multiple_reports_batch(self, tmp_path):
        for i in range(3):
            _write_report(tmp_path, f"report_20260312_10000{i}.json", {
                "status": "pending", "category": "emissions",
                "entity": f"Smoky{i}", "description": "Black smoke",
            })
        results = process_pending_reports()
        assert results["processed"] == 3
        assert len(results["cases_created"]) == 3


# ── get_unprocessed_scans ────────────────────────────────────

class TestGetUnprocessedScans:
    def test_no_scans_dir(self):
        assert get_unprocessed_scans() == []

    def test_finds_unprocessed(self, tmp_path):
        _write_scan(tmp_path, "google_reviews_20260312.json", {
            "channel_id": "google_reviews", "signals": [],
        })
        _write_scan(tmp_path, "yelp_20260312.json", {
            "channel_id": "yelp", "signals": [],
            "processed_at": "2026-03-12T10:00:00",
        })
        scans = get_unprocessed_scans()
        assert len(scans) == 1
        assert scans[0][1]["channel_id"] == "google_reviews"


# ── process_scan_results ─────────────────────────────────────

class TestProcessScanResults:
    @pytest.fixture(autouse=True)
    def _mock_escalation(self, monkeypatch):
        self._case_counter = 0

        def fake_create_case(**kwargs):
            self._case_counter += 1
            return self._case_counter

        monkeypatch.setattr(intake_mod, "init_escalation_db", lambda: None)
        monkeypatch.setattr(intake_mod, "create_case", fake_create_case)

    def test_no_scans(self):
        results = process_scan_results()
        assert results["scans_processed"] == 0

    def test_processes_scan_with_signals(self, tmp_path):
        _write_scan(tmp_path, "google_20260312.json", {
            "channel_id": "google_reviews",
            "target_fields": ["used_car_dealers"],
            "signals": [
                {"entity": "Shady Motors", "description": "Fraud reported", "severity": 5},
                {"entity": "Good Dealer", "description": "Minor issue", "severity": 2},
            ],
        })
        results = process_scan_results()
        assert results["scans_processed"] == 1
        assert results["signals_found"] == 2
        assert len(results["cases_created"]) == 2

    def test_skips_signals_without_entity(self, tmp_path):
        _write_scan(tmp_path, "scan_20260312.json", {
            "channel_id": "news",
            "target_fields": ["fleet_compliance"],
            "signals": [
                {"description": "General article", "severity": 1},  # no entity
                {"entity": "Bad Trucking", "description": "Violations", "severity": 3},
            ],
        })
        results = process_scan_results()
        assert results["signals_found"] == 1

    def test_skips_signals_without_description(self, tmp_path):
        _write_scan(tmp_path, "scan_20260312.json", {
            "channel_id": "news",
            "target_fields": ["fleet_compliance"],
            "signals": [
                {"entity": "Some Co"},  # no description
            ],
        })
        results = process_scan_results()
        assert results["signals_found"] == 0

    def test_marks_scan_as_processed(self, tmp_path):
        _write_scan(tmp_path, "scan_20260312.json", {
            "channel_id": "test", "target_fields": [], "signals": [],
        })
        process_scan_results()

        data = json.loads(
            (tmp_path / "intake" / "scans" / "scan_20260312.json").read_text()
        )
        assert "processed_at" in data

    def test_signal_uses_own_field(self, tmp_path, monkeypatch):
        calls = []

        def capture_create(**kwargs):
            calls.append(kwargs)
            return 1

        monkeypatch.setattr(intake_mod, "create_case", capture_create)
        _write_scan(tmp_path, "scan.json", {
            "channel_id": "cfpb",
            "target_fields": ["dealer_financing"],
            "signals": [
                {"entity": "Lender", "description": "Predatory",
                 "field": "auto_insurance"},
            ],
        })
        process_scan_results()
        assert calls[0]["field"] == "auto_insurance"

    def test_signal_falls_back_to_primary_field(self, tmp_path, monkeypatch):
        calls = []

        def capture_create(**kwargs):
            calls.append(kwargs)
            return 1

        monkeypatch.setattr(intake_mod, "create_case", capture_create)
        _write_scan(tmp_path, "scan.json", {
            "channel_id": "cfpb",
            "target_fields": ["dealer_financing"],
            "signals": [
                {"entity": "Lender", "description": "Issue"},
            ],
        })
        process_scan_results()
        assert calls[0]["field"] == "dealer_financing"

    def test_empty_signals_still_marks_processed(self, tmp_path):
        _write_scan(tmp_path, "scan.json", {
            "channel_id": "test", "target_fields": [], "signals": [],
        })
        results = process_scan_results()
        assert results["scans_processed"] == 1
        assert results["signals_found"] == 0


# ── intake_summary ───────────────────────────────────────────

class TestIntakeSummary:
    def test_empty_results(self):
        report_r = {"processed": 0, "invalid": 0, "skipped": 0,
                     "errors": [], "cases_created": []}
        scan_r = {"scans_processed": 0, "signals_found": 0, "cases_created": []}
        text = intake_summary(report_r, scan_r)
        assert "Daily Intake Summary" in text
        assert "Total new cases: 0" in text

    def test_with_results(self):
        report_r = {
            "processed": 2, "invalid": 1, "skipped": 0,
            "errors": [{"file": "report_1.json", "errors": ["Missing entity"]}],
            "cases_created": [
                {"case_id": 1, "entity": "Bad Co", "field": "tow_companies", "severity": 3},
            ],
        }
        scan_r = {
            "scans_processed": 5, "signals_found": 3,
            "cases_created": [
                {"case_id": 2, "entity": "Shady", "field": "used_car_dealers", "channel": "google"},
            ],
        }
        text = intake_summary(report_r, scan_r)
        assert "Processed: 2" in text
        assert "Invalid:   1" in text
        assert "Bad Co" in text
        assert "Shady" in text
        assert "Total new cases: 2" in text

    def test_shows_validation_errors(self):
        report_r = {
            "processed": 0, "invalid": 1, "skipped": 0,
            "errors": [{"file": "bad.json", "errors": ["Missing entity", "Empty desc"]}],
            "cases_created": [],
        }
        scan_r = {"scans_processed": 0, "signals_found": 0, "cases_created": []}
        text = intake_summary(report_r, scan_r)
        assert "bad.json" in text
        assert "Missing entity" in text


# ── run_daily_intake ─────────────────────────────────────────

class TestRunDailyIntake:
    @pytest.fixture(autouse=True)
    def _mock_escalation(self, monkeypatch):
        self._counter = 0

        def fake_create(**kwargs):
            self._counter += 1
            return self._counter

        monkeypatch.setattr(intake_mod, "init_escalation_db", lambda: None)
        monkeypatch.setattr(intake_mod, "create_case", fake_create)

    def test_full_pipeline(self, tmp_path):
        _write_report(tmp_path, "report_20260312_100000.json", {
            "status": "pending", "category": "tow_company",
            "entity": "Tow Co", "description": "Predatory",
        })
        _write_scan(tmp_path, "scan_20260312.json", {
            "channel_id": "google", "target_fields": ["auto_repair"],
            "signals": [
                {"entity": "Bad Shop", "description": "Fraud", "severity": 4},
            ],
        })

        summary, report_r, scan_r = run_daily_intake()
        assert report_r["processed"] == 1
        assert scan_r["signals_found"] == 1
        assert "Total new cases: 2" in summary

    def test_empty_pipeline(self):
        summary, report_r, scan_r = run_daily_intake()
        assert report_r["processed"] == 0
        assert scan_r["scans_processed"] == 0
        assert "Total new cases: 0" in summary
