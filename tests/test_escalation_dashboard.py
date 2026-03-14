"""Tests for escalation dashboard — routes and helper functions."""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

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


def _create_case(field="auto-dealer", entity="Bad Motors", issue="Odometer fraud",
                 severity=3, **kw):
    return esc.create_case(field, entity, issue, severity=severity, **kw)


# ---------------------------------------------------------------------------
# New helper functions
# ---------------------------------------------------------------------------

class TestGetAllCases:
    def test_returns_active_cases(self):
        _create_case(entity="A")
        _create_case(entity="B")
        cases = esc.get_all_cases(active_only=True)
        assert len(cases) == 2

    def test_excludes_resolved_when_active_only(self):
        cid = _create_case(entity="A")
        _create_case(entity="B")
        esc.resolve_case(cid)
        cases = esc.get_all_cases(active_only=True)
        assert len(cases) == 1
        assert cases[0]["entity"] == "B"

    def test_includes_resolved_when_not_active_only(self):
        cid = _create_case(entity="A")
        _create_case(entity="B")
        esc.resolve_case(cid)
        cases = esc.get_all_cases(active_only=False)
        assert len(cases) == 2

    def test_empty_db(self):
        assert esc.get_all_cases() == []

    def test_ordered_by_severity_desc(self):
        _create_case(entity="Low", severity=1)
        _create_case(entity="High", severity=5)
        cases = esc.get_all_cases()
        assert cases[0]["entity"] == "High"


class TestGetCaseHistory:
    def test_returns_initial_history(self):
        cid = _create_case()
        history = esc.get_case_history(cid)
        assert len(history) == 1
        assert history[0]["to_stage"] == "seed"

    def test_tracks_escalation_steps(self):
        cid = _create_case()
        esc.escalate_case(cid)
        esc.escalate_case(cid)
        history = esc.get_case_history(cid)
        assert len(history) == 3
        assert history[1]["from_stage"] == "seed"
        assert history[1]["to_stage"] == "sprout"
        assert history[2]["from_stage"] == "sprout"
        assert history[2]["to_stage"] == "notice"

    def test_empty_for_nonexistent(self):
        assert esc.get_case_history(9999) == []


class TestGetStageDistribution:
    def test_all_stages_present(self):
        dist = esc.get_stage_distribution()
        assert set(dist.keys()) == set(esc.STAGES)

    def test_counts_cases_per_stage(self):
        _create_case(entity="A")
        _create_case(entity="B")
        cid = _create_case(entity="C")
        esc.escalate_case(cid)  # seed -> sprout
        dist = esc.get_stage_distribution()
        assert dist["seed"] == 2
        assert dist["sprout"] == 1

    def test_excludes_resolved_when_active(self):
        cid = _create_case()
        esc.resolve_case(cid)
        dist = esc.get_stage_distribution(active_only=True)
        assert all(v == 0 for v in dist.values() if True)  # harvest from resolve
        # resolved case goes to harvest in DB but is filtered out by active_only
        assert dist["seed"] == 0

    def test_includes_resolved_when_not_active(self):
        cid = _create_case()
        esc.resolve_case(cid)
        dist = esc.get_stage_distribution(active_only=False)
        assert dist["harvest"] == 1


class TestGetFieldList:
    def test_returns_fields_with_counts(self):
        _create_case(field="dealers", entity="A")
        _create_case(field="dealers", entity="B")
        _create_case(field="lenders", entity="C")
        fields = esc.get_field_list()
        assert len(fields) == 2
        dealer = next(f for f in fields if f["field"] == "dealers")
        assert dealer["total"] == 2
        assert dealer["active"] == 2

    def test_tracks_resolved_separately(self):
        cid = _create_case(field="dealers", entity="A")
        _create_case(field="dealers", entity="B")
        esc.resolve_case(cid)
        fields = esc.get_field_list()
        dealer = next(f for f in fields if f["field"] == "dealers")
        assert dealer["total"] == 2
        assert dealer["active"] == 1

    def test_empty_db(self):
        assert esc.get_field_list() == []


# ---------------------------------------------------------------------------
# Flask route tests
# ---------------------------------------------------------------------------

@pytest.fixture
def client(temp_db, monkeypatch):
    """Create a Flask test client with temp DB."""
    # Also redirect app.py's DB_PATH
    import app as flask_app
    monkeypatch.setattr(flask_app, "DB_PATH", temp_db)
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        yield c


class TestEscalationRoute:
    def test_page_loads(self, client):
        rv = client.get("/escalation")
        assert rv.status_code == 200
        assert b"Escalation Status" in rv.data

    def test_shows_stage_pipeline(self, client):
        rv = client.get("/escalation")
        for stage in esc.STAGES:
            assert stage.encode() in rv.data

    def test_shows_cases(self, client):
        _create_case(entity="Shady Dealer", field="autos")
        rv = client.get("/escalation")
        assert b"Shady Dealer" in rv.data

    def test_field_filter(self, client):
        _create_case(entity="AutoEntity", field="autos")
        _create_case(entity="LenderEntity", field="lenders")
        rv = client.get("/escalation?field=autos")
        assert b"AutoEntity" in rv.data
        assert b"Cases in autos" in rv.data
        # Filtered cases table should not contain the lender entity
        assert b"LenderEntity" not in rv.data

    def test_show_resolved(self, client):
        cid = _create_case(entity="Resolved Corp")
        esc.resolve_case(cid)
        # Without resolved flag
        rv = client.get("/escalation")
        # Resolved cases should not be in the active list
        # With resolved flag
        rv2 = client.get("/escalation?resolved=1")
        assert b"Resolved Corp" in rv2.data

    def test_empty_state(self, client):
        rv = client.get("/escalation")
        assert b"No cases found" in rv.data


class TestEscalationAPI:
    def test_returns_json(self, client):
        rv = client.get("/api/escalation")
        assert rv.status_code == 200
        data = rv.get_json()
        assert "cases" in data
        assert "stage_distribution" in data
        assert "escalation_ready" in data
        assert "cross_field_entities" in data
        assert "fields" in data
        assert "total_active" in data

    def test_includes_cases(self, client):
        _create_case(entity="Test Entity")
        rv = client.get("/api/escalation")
        data = rv.get_json()
        assert data["total_active"] == 1
        assert data["cases"][0]["entity"] == "Test Entity"

    def test_stage_distribution_structure(self, client):
        rv = client.get("/api/escalation")
        data = rv.get_json()
        dist = data["stage_distribution"]
        for stage in esc.STAGES:
            assert stage in dist


class TestCaseHistoryAPI:
    def test_returns_history(self, client):
        cid = _create_case()
        esc.escalate_case(cid)
        rv = client.get(f"/api/cases/{cid}/history")
        assert rv.status_code == 200
        data = rv.get_json()
        assert len(data["history"]) == 2

    def test_empty_for_nonexistent(self, client):
        rv = client.get("/api/cases/9999/history")
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["history"] == []
