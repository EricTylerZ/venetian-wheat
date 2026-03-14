"""Tests for wheat/field_manager.py — field lifecycle and DB operations."""

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _make_config(**overrides):
    """Minimal config for FieldManager construction."""
    base = {
        "llm_api": "venice",
        "max_tokens": 100,
        "timeout": 10,
        "seeds_per_run": 2,
        "lifespan": 60,
        "strategist_prompt": "Generate {seeds_per_run} tasks. {stewards_map} {file_contents} {guidance}",
        "coder_prompt": "Code: {task} {stewards_map} {file_contents}",
        "models": {"strategist": "test-model", "coder": "test-coder", "rescuer": "test-coder"},
    }
    base.update(overrides)
    return base


def _init_db(db_path):
    """Create the schema FieldManager expects."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        log TEXT DEFAULT '',
        project_id TEXT DEFAULT 'default',
        prompt_tokens INTEGER DEFAULT 0,
        completion_tokens INTEGER DEFAULT 0,
        total_tokens INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS seeds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER,
        seed_id TEXT,
        task TEXT,
        status TEXT,
        output TEXT,
        code_file TEXT,
        test_result TEXT,
        project_id TEXT DEFAULT 'default'
    )""")
    conn.commit()
    conn.close()


@pytest.fixture(autouse=True)
def mock_deps(tmp_path, monkeypatch):
    """Mock heavy dependencies so tests don't hit APIs or real config."""
    # Mock TokenSteward
    mock_ts = MagicMock()
    mock_ts.can_water.return_value = True
    monkeypatch.setattr("wheat.sower.TokenSteward", lambda: mock_ts)
    monkeypatch.setattr("wheat.wheat_seed.TokenSteward", lambda: mock_ts)

    # Mock provider
    mock_prov = MagicMock()
    mock_prov.generate.return_value = ("task_a\ntask_b", {"prompt_tokens": 5, "completion_tokens": 10})
    monkeypatch.setattr("wheat.sower.get_provider", lambda cfg: mock_prov)
    monkeypatch.setattr("wheat.wheat_seed.get_provider", lambda cfg: mock_prov)

    # Redirect DB
    db_path = str(tmp_path / "test_wheat.db")
    _init_db(db_path)
    import wheat.field_manager as fm
    monkeypatch.setattr(fm, "DB_PATH", db_path)

    # Mock WheatSeed's save_progress to use temp DB
    def mock_save_progress(self):
        conn = sqlite3.connect(db_path, timeout=15)
        try:
            c = conn.cursor()
            c.execute("UPDATE seeds SET status=?, output=?, code_file=?, test_result=? WHERE seed_id=? AND project_id=?",
                      (self.progress["status"], json.dumps(self.progress["output"]),
                       self.progress["code_file"], self.progress["test_result"],
                       self.seed_id, self.project_id))
            conn.commit()
        finally:
            conn.close()
    monkeypatch.setattr("wheat.wheat_seed.WheatSeed.save_progress", mock_save_progress)

    # Mock get_map_as_string
    monkeypatch.setattr("wheat.field_manager.get_map_as_string", lambda **kw: "mock_stewards_map")

    # Mock load_project_config to return our test config
    monkeypatch.setattr("wheat.field_manager.load_project_config", lambda pid: _make_config())

    return {"db_path": db_path, "provider": mock_prov, "token_steward": mock_ts}


# --- create_seed ---

class TestCreateSeed:
    def test_create_seed_basic(self, mock_deps):
        from wheat.field_manager import FieldManager
        fm = FieldManager(project_id="test", config=_make_config())
        seed = fm.create_seed("1", "build widget", "Growing", "[]", "", "")
        assert seed.task == "build widget"
        assert seed.seed_id == "1"
        assert seed.progress["status"] == "Growing"

    def test_create_seed_with_output(self, mock_deps):
        from wheat.field_manager import FieldManager
        fm = FieldManager(project_id="test", config=_make_config())
        output_json = json.dumps(["line1", "line2"])
        seed = fm.create_seed("2", "task2", "Fruitful", output_json, "/tmp/code.py", "OK")
        assert seed.progress["output"] == ["line1", "line2"]
        assert seed.progress["code_file"] == "/tmp/code.py"
        assert seed.progress["test_result"] == "OK"

    def test_create_seed_with_coder_prompt(self, mock_deps):
        from wheat.field_manager import FieldManager
        fm = FieldManager(project_id="test", config=_make_config())
        seed = fm.create_seed("3", "task3", "Growing", "[]", "", "", coder_prompt="custom prompt")
        assert seed.coder_prompt == "custom prompt"

    def test_create_seed_null_output(self, mock_deps):
        from wheat.field_manager import FieldManager
        fm = FieldManager(project_id="test", config=_make_config())
        seed = fm.create_seed("4", "task4", "Growing", None, None, None)
        assert seed.progress["output"] == []
        assert seed.progress["code_file"] == ""
        assert seed.progress["test_result"] == ""


# --- sow_field ---

class TestSowField:
    def test_sow_field_inserts_run(self, mock_deps):
        from wheat.field_manager import FieldManager
        fm = FieldManager(project_id="test_proj", config=_make_config())
        fm.sow_field()

        conn = sqlite3.connect(mock_deps["db_path"])
        c = conn.cursor()
        c.execute("SELECT project_id FROM runs")
        rows = c.fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][0] == "test_proj"

    def test_sow_field_inserts_seeds(self, mock_deps):
        from wheat.field_manager import FieldManager
        fm = FieldManager(project_id="test_proj", config=_make_config(seeds_per_run=2))
        fm.sow_field()

        conn = sqlite3.connect(mock_deps["db_path"])
        c = conn.cursor()
        c.execute("SELECT task, status, project_id FROM seeds ORDER BY seed_id")
        rows = c.fetchall()
        conn.close()
        assert len(rows) == 2
        assert rows[0][1] == "Growing"
        assert rows[0][2] == "test_proj"

    def test_sow_field_populates_self_seeds(self, mock_deps):
        from wheat.field_manager import FieldManager
        fm = FieldManager(project_id="test", config=_make_config(seeds_per_run=2))
        fm.sow_field()
        assert len(fm.seeds) == 2
        assert all(hasattr(s, "task") for s in fm.seeds)

    def test_sow_field_with_coder_prompt(self, mock_deps):
        from wheat.field_manager import FieldManager
        fm = FieldManager(project_id="test", config=_make_config(seeds_per_run=1))
        fm.sow_field(coder_prompt="Build {task} using {stewards_map} with {file_contents}")
        assert len(fm.seeds) == 1
        # coder_prompt should be formatted with task and stewards_map
        prompt = fm.seeds[0].coder_prompt
        assert "mock_stewards_map" in prompt

    def test_sow_field_without_coder_prompt(self, mock_deps):
        from wheat.field_manager import FieldManager
        fm = FieldManager(project_id="test", config=_make_config(seeds_per_run=1))
        fm.sow_field(coder_prompt=None)
        assert fm.seeds[0].coder_prompt is None

    def test_sow_field_run_log_includes_task_count(self, mock_deps):
        from wheat.field_manager import FieldManager
        fm = FieldManager(project_id="test", config=_make_config(seeds_per_run=2))
        fm.sow_field()

        conn = sqlite3.connect(mock_deps["db_path"])
        c = conn.cursor()
        c.execute("SELECT log FROM runs LIMIT 1")
        log = c.fetchone()[0]
        conn.close()
        assert "Sowed 2 seeds" in log

    def test_sow_field_rollback_on_error(self, mock_deps):
        from wheat.field_manager import FieldManager
        fm = FieldManager(project_id="test", config=_make_config())
        # Make sow_seeds raise after run insert
        with patch.object(fm.sower, "sow_seeds", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError):
                fm.sow_field()
        # Run row may exist but seeds should not
        conn = sqlite3.connect(mock_deps["db_path"])
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM seeds")
        count = c.fetchone()[0]
        conn.close()
        assert count == 0


# --- FieldManager init ---

class TestFieldManagerInit:
    def test_default_project_id(self, mock_deps):
        from wheat.field_manager import FieldManager
        fm = FieldManager(config=_make_config())
        assert fm.project_id == "default"

    def test_custom_project_id(self, mock_deps):
        from wheat.field_manager import FieldManager
        fm = FieldManager(project_id="my_project", config=_make_config())
        assert fm.project_id == "my_project"

    def test_seeds_per_run_from_config(self, mock_deps):
        from wheat.field_manager import FieldManager
        fm = FieldManager(config=_make_config(seeds_per_run=5))
        assert fm.seeds_per_run == 5

    def test_seeds_start_empty(self, mock_deps):
        from wheat.field_manager import FieldManager
        fm = FieldManager(config=_make_config())
        assert fm.seeds == []
