"""Tests for wheat/escalation.py — subsidiarity-based escalation engine."""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import wheat.escalation as esc


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Redirect all escalation DB operations to a temp database."""
    db_path = str(tmp_path / "test_wheat.db")
    monkeypatch.setattr(esc, "DB_PATH", db_path)
    esc.init_escalation_db()
    return db_path


# --- Constants ---

class TestStages:
    """Verify stage definitions and wait times."""

    def test_stage_order(self):
        assert esc.STAGES == [
            "seed", "sprout", "notice", "virtue",
            "community", "demand", "civil", "harvest",
        ]

    def test_stage_count(self):
        assert len(esc.STAGES) == 8

    def test_all_stages_have_wait_days(self):
        # Every stage except harvest should have a wait time
        for stage in esc.STAGES[:-1]:
            assert stage in esc.STAGE_WAIT_DAYS, f"Missing wait days for {stage}"

    def test_harvest_has_no_wait(self):
        assert "harvest" not in esc.STAGE_WAIT_DAYS

    def test_notice_gives_two_weeks(self):
        assert esc.STAGE_WAIT_DAYS["notice"] == 14

    def test_virtue_gives_thirty_days(self):
        assert esc.STAGE_WAIT_DAYS["virtue"] == 30

    def test_civil_gives_ninety_days(self):
        assert esc.STAGE_WAIT_DAYS["civil"] == 90


# --- Database initialization ---

class TestInitDB:
    """Verify DB schema creation."""

    def test_creates_cases_table(self, temp_db):
        import sqlite3
        conn = sqlite3.connect(temp_db)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        conn.close()
        assert "cases" in table_names

    def test_creates_history_table(self, temp_db):
        import sqlite3
        conn = sqlite3.connect(temp_db)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        conn.close()
        assert "case_history" in table_names

    def test_idempotent(self, temp_db):
        # Calling init_escalation_db twice should not error
        esc.init_escalation_db()
        esc.init_escalation_db()


# --- Case creation ---

class TestCreateCase:
    """Test case creation at SEED stage."""

    def test_returns_case_id(self):
        case_id = esc.create_case("fleet_compliance", "Acme Towing", "Expired license")
        assert isinstance(case_id, int)
        assert case_id > 0

    def test_starts_at_seed(self, temp_db):
        import sqlite3
        case_id = esc.create_case("fleet_compliance", "Acme Towing", "Expired license")
        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT stage FROM cases WHERE id = ?", (case_id,)).fetchone()
        conn.close()
        assert row[0] == "seed"

    def test_stores_fields(self, temp_db):
        import sqlite3
        case_id = esc.create_case(
            "auto_repair", "Bad Mechanic", "Unlicensed work",
            severity=3, law_cited="CRS 12-6-120", source="BBB complaint",
            notes="Multiple complaints",
        )
        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        conn.close()
        # field=1, entity=2, issue=3, severity=4
        assert row[1] == "auto_repair"
        assert row[2] == "Bad Mechanic"
        assert row[3] == "Unlicensed work"
        assert row[4] == 3

    def test_sets_escalation_deadline(self, temp_db):
        import sqlite3
        case_id = esc.create_case("tow_companies", "Shady Tow", "Predatory towing")
        conn = sqlite3.connect(temp_db)
        row = conn.execute(
            "SELECT escalation_deadline FROM cases WHERE id = ?", (case_id,)
        ).fetchone()
        conn.close()
        deadline = datetime.fromisoformat(row[0])
        # Seed wait is 1 day, so deadline should be roughly 1 day from now
        assert deadline > datetime.now()
        assert deadline < datetime.now() + timedelta(days=2)

    def test_creates_history_entry(self, temp_db):
        import sqlite3
        case_id = esc.create_case("emissions", "Polluter Inc", "Excess emissions")
        conn = sqlite3.connect(temp_db)
        history = conn.execute(
            "SELECT to_stage, reason FROM case_history WHERE case_id = ?", (case_id,)
        ).fetchall()
        conn.close()
        assert len(history) == 1
        assert history[0][0] == "seed"
        assert "Initial signal" in history[0][1]

    def test_default_severity_is_one(self, temp_db):
        import sqlite3
        case_id = esc.create_case("parking", "Boot Co", "Illegal booting")
        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT severity FROM cases WHERE id = ?", (case_id,)).fetchone()
        conn.close()
        assert row[0] == 1

    def test_evidence_stored_as_json(self, temp_db):
        import sqlite3
        case_id = esc.create_case("auto_insurance", "Scam Insurance", "Fake policies",
                                  source="consumer complaint")
        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT evidence FROM cases WHERE id = ?", (case_id,)).fetchone()
        conn.close()
        evidence = json.loads(row[0])
        assert isinstance(evidence, list)
        assert len(evidence) == 1
        assert evidence[0]["issue"] == "Fake policies"
        assert evidence[0]["source"] == "consumer complaint"


# --- Duplicate detection ---

class TestDuplicateDetection:
    """Test that duplicate signals merge into existing cases."""

    def test_same_entity_field_merges(self):
        id1 = esc.create_case("fleet_compliance", "Acme Towing", "Issue 1")
        id2 = esc.create_case("fleet_compliance", "Acme Towing", "Issue 2")
        assert id1 == id2  # Same case

    def test_different_field_creates_new(self):
        id1 = esc.create_case("fleet_compliance", "Acme Towing", "Issue 1")
        id2 = esc.create_case("auto_repair", "Acme Towing", "Issue 2")
        assert id1 != id2  # Different fields = different cases

    def test_merge_adds_evidence(self, temp_db):
        import sqlite3
        case_id = esc.create_case("tow_companies", "Bad Tow", "First complaint")
        esc.create_case("tow_companies", "Bad Tow", "Second complaint")
        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT evidence FROM cases WHERE id = ?", (case_id,)).fetchone()
        conn.close()
        evidence = json.loads(row[0])
        assert len(evidence) == 2

    def test_merge_bumps_severity(self, temp_db):
        import sqlite3
        case_id = esc.create_case("tow_companies", "Bad Tow", "Low issue", severity=2)
        esc.create_case("tow_companies", "Bad Tow", "High issue", severity=7)
        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT severity FROM cases WHERE id = ?", (case_id,)).fetchone()
        conn.close()
        assert row[0] == 7  # Bumped to higher severity

    def test_merge_keeps_higher_severity(self, temp_db):
        import sqlite3
        case_id = esc.create_case("tow_companies", "Bad Tow", "High issue", severity=8)
        esc.create_case("tow_companies", "Bad Tow", "Low issue", severity=2)
        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT severity FROM cases WHERE id = ?", (case_id,)).fetchone()
        conn.close()
        assert row[0] == 8  # Stays at 8, not downgraded

    def test_resolved_case_allows_new(self, temp_db):
        id1 = esc.create_case("fleet_compliance", "Acme Towing", "Old issue")
        esc.resolve_case(id1, "Fixed")
        id2 = esc.create_case("fleet_compliance", "Acme Towing", "New issue")
        assert id1 != id2  # New case since old one resolved


# --- Escalation ---

class TestEscalation:
    """Test stage progression."""

    def test_seed_to_sprout(self, temp_db):
        import sqlite3
        case_id = esc.create_case("fleet_compliance", "Acme", "Issue")
        esc.escalate_case(case_id, "Validated")
        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT stage FROM cases WHERE id = ?", (case_id,)).fetchone()
        conn.close()
        assert row[0] == "sprout"

    def test_full_escalation_path(self, temp_db):
        import sqlite3
        case_id = esc.create_case("fleet_compliance", "Acme", "Issue")
        expected = ["sprout", "notice", "virtue", "community", "demand", "civil", "harvest"]
        for stage in expected:
            esc.escalate_case(case_id, f"Escalating to {stage}")
            conn = sqlite3.connect(temp_db)
            row = conn.execute("SELECT stage FROM cases WHERE id = ?", (case_id,)).fetchone()
            conn.close()
            assert row[0] == stage

    def test_escalation_records_history(self, temp_db):
        import sqlite3
        case_id = esc.create_case("fleet_compliance", "Acme", "Issue")
        esc.escalate_case(case_id, "Evidence found")
        conn = sqlite3.connect(temp_db)
        history = conn.execute(
            "SELECT from_stage, to_stage, reason FROM case_history WHERE case_id = ? ORDER BY id",
            (case_id,),
        ).fetchall()
        conn.close()
        assert len(history) == 2  # seed creation + escalation
        assert history[1][0] == "seed"
        assert history[1][1] == "sprout"
        assert history[1][2] == "Evidence found"

    def test_escalation_updates_deadline(self, temp_db):
        import sqlite3
        case_id = esc.create_case("fleet_compliance", "Acme", "Issue")
        esc.escalate_case(case_id)
        conn = sqlite3.connect(temp_db)
        row = conn.execute(
            "SELECT escalation_deadline FROM cases WHERE id = ?", (case_id,)
        ).fetchone()
        conn.close()
        deadline = datetime.fromisoformat(row[0])
        # Sprout wait is 3 days
        assert deadline > datetime.now() + timedelta(days=2)
        assert deadline < datetime.now() + timedelta(days=4)

    def test_harvest_cannot_escalate(self):
        case_id = esc.create_case("fleet_compliance", "Acme", "Issue")
        for _ in range(7):  # seed → harvest
            esc.escalate_case(case_id)
        # Already at harvest — should not raise, just print
        esc.escalate_case(case_id)  # No error

    def test_invalid_case_raises(self):
        with pytest.raises(ValueError, match="not found"):
            esc.escalate_case(99999)


# --- Resolution ---

class TestResolution:
    """Test case resolution."""

    def test_resolve_sets_harvest(self, temp_db):
        import sqlite3
        case_id = esc.create_case("fleet_compliance", "Acme", "Issue")
        esc.resolve_case(case_id, "Compliance achieved")
        conn = sqlite3.connect(temp_db)
        row = conn.execute(
            "SELECT stage, resolved_at, resolution FROM cases WHERE id = ?", (case_id,)
        ).fetchone()
        conn.close()
        assert row[0] == "harvest"
        assert row[1] is not None  # resolved_at set
        assert row[2] == "Compliance achieved"

    def test_resolve_records_history(self, temp_db):
        import sqlite3
        case_id = esc.create_case("fleet_compliance", "Acme", "Issue")
        esc.escalate_case(case_id)  # → sprout
        esc.resolve_case(case_id, "Fixed it")
        conn = sqlite3.connect(temp_db)
        history = conn.execute(
            "SELECT from_stage, to_stage, reason FROM case_history WHERE case_id = ? ORDER BY id DESC LIMIT 1",
            (case_id,),
        ).fetchone()
        conn.close()
        assert history[0] == "sprout"
        assert history[1] == "harvest"
        assert history[2] == "Fixed it"

    def test_resolve_invalid_case_raises(self):
        with pytest.raises(ValueError, match="not found"):
            esc.resolve_case(99999)

    def test_early_resolution(self, temp_db):
        """Cases can be resolved at any stage (entity complied early)."""
        import sqlite3
        case_id = esc.create_case("fleet_compliance", "Good Actor", "Minor issue")
        esc.resolve_case(case_id, "Immediately corrected")
        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT stage, resolved_at FROM cases WHERE id = ?", (case_id,)).fetchone()
        conn.close()
        assert row[0] == "harvest"
        assert row[1] is not None


# --- Queries ---

class TestQueries:
    """Test case retrieval functions."""

    def test_get_cases_by_field(self):
        esc.create_case("fleet_compliance", "Acme", "Issue 1")
        esc.create_case("fleet_compliance", "Beta", "Issue 2")
        esc.create_case("auto_repair", "Gamma", "Issue 3")
        cases = esc.get_cases_by_field("fleet_compliance")
        assert len(cases) == 2

    def test_active_only_excludes_resolved(self):
        case_id = esc.create_case("fleet_compliance", "Acme", "Issue")
        esc.resolve_case(case_id, "Done")
        esc.create_case("fleet_compliance", "Beta", "Issue 2")
        active = esc.get_cases_by_field("fleet_compliance", active_only=True)
        all_cases = esc.get_cases_by_field("fleet_compliance", active_only=False)
        assert len(active) == 1
        assert len(all_cases) == 2

    def test_get_escalation_ready_none(self):
        esc.create_case("fleet_compliance", "Acme", "Issue")
        # Just created — deadline is in the future
        ready = esc.get_escalation_ready()
        assert len(ready) == 0

    def test_get_escalation_ready_past_deadline(self, temp_db):
        import sqlite3
        case_id = esc.create_case("fleet_compliance", "Acme", "Issue")
        # Manually set deadline to the past
        past = (datetime.now() - timedelta(days=5)).isoformat()
        conn = sqlite3.connect(temp_db)
        conn.execute("UPDATE cases SET escalation_deadline = ? WHERE id = ?", (past, case_id))
        conn.commit()
        conn.close()
        ready = esc.get_escalation_ready()
        assert len(ready) == 1
        assert ready[0]["id"] == case_id

    def test_resolved_not_in_escalation_ready(self, temp_db):
        import sqlite3
        case_id = esc.create_case("fleet_compliance", "Acme", "Issue")
        past = (datetime.now() - timedelta(days=5)).isoformat()
        conn = sqlite3.connect(temp_db)
        conn.execute("UPDATE cases SET escalation_deadline = ? WHERE id = ?", (past, case_id))
        conn.commit()
        conn.close()
        esc.resolve_case(case_id, "Done")
        ready = esc.get_escalation_ready()
        assert len(ready) == 0


# --- Cross-field pattern detection ---

class TestCrossFieldPatterns:
    """Test entity appearing across multiple fields."""

    def test_no_cross_field(self):
        esc.create_case("fleet_compliance", "Acme", "Issue 1")
        esc.create_case("auto_repair", "Beta", "Issue 2")
        cross = esc.get_cross_field_entities()
        assert len(cross) == 0

    def test_detects_cross_field(self):
        esc.create_case("fleet_compliance", "Bad Actor", "Issue 1")
        esc.create_case("auto_repair", "Bad Actor", "Issue 2")
        cross = esc.get_cross_field_entities()
        assert len(cross) == 1
        assert cross[0]["entity"] == "Bad Actor"
        assert cross[0]["field_count"] == 2
        assert set(cross[0]["fields"]) == {"fleet_compliance", "auto_repair"}

    def test_three_fields(self):
        esc.create_case("fleet_compliance", "Serial Offender", "Issue 1")
        esc.create_case("auto_repair", "Serial Offender", "Issue 2")
        esc.create_case("emissions", "Serial Offender", "Issue 3")
        cross = esc.get_cross_field_entities()
        assert cross[0]["field_count"] == 3

    def test_resolved_still_counted(self):
        """Resolved cases should NOT appear in cross-field (active only)."""
        id1 = esc.create_case("fleet_compliance", "Reformed Actor", "Issue 1")
        esc.create_case("auto_repair", "Reformed Actor", "Issue 2")
        esc.resolve_case(id1)
        cross = esc.get_cross_field_entities()
        # Only 1 active case in auto_repair — not cross-field anymore
        assert len(cross) == 0


# --- Daily escalation check ---

class TestDailyCheck:
    """Test the daily briefing report."""

    def test_empty_report(self):
        report = esc.daily_escalation_check()
        assert "No escalations" in report

    def test_reports_ready_cases(self, temp_db):
        import sqlite3
        case_id = esc.create_case("fleet_compliance", "Acme", "Issue", severity=3)
        past = (datetime.now() - timedelta(days=5)).isoformat()
        conn = sqlite3.connect(temp_db)
        conn.execute("UPDATE cases SET escalation_deadline = ? WHERE id = ?", (past, case_id))
        conn.commit()
        conn.close()
        report = esc.daily_escalation_check()
        assert "ESCALATION READY" in report
        assert "Acme" in report

    def test_reports_cross_field(self):
        esc.create_case("fleet_compliance", "Bad Actor", "Issue 1")
        esc.create_case("auto_repair", "Bad Actor", "Issue 2")
        report = esc.daily_escalation_check()
        assert "CROSS-FIELD" in report
        assert "Bad Actor" in report
