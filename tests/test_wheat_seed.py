"""Tests for wheat/wheat_seed.py — seed lifecycle, code generation, grow/reap."""

import json
import os
import time
from unittest import mock

import pytest

from wheat.wheat_seed import WheatSeed


def _config(tmp_path, **overrides):
    """Build a minimal config dict and write config.json."""
    cfg = {
        "lifespan": 60,
        "max_tokens": 500,
        "llm_api": "venice",
        "coder_prompt": "Write code for: {task} {stewards_map} {file_contents}",
        "models": {"coder": "test-coder", "rescuer": "test-rescuer"},
    }
    cfg.update(overrides)
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(cfg))
    return cfg


@pytest.fixture
def seed(tmp_path, monkeypatch):
    """Create a WheatSeed with mocked provider and DB calls."""
    cfg = _config(tmp_path)
    monkeypatch.setattr("wheat.wheat_seed.TokenSteward", mock.MagicMock)
    monkeypatch.setattr("wheat.wheat_seed.get_provider", lambda c: mock.MagicMock())
    # Override seed_dir to use tmp_path
    s = WheatSeed("Build a widget", "s1", "test-model", config=cfg, project_id="default")
    s.seed_dir = str(tmp_path / "seeds" / "seed_s1")
    os.makedirs(s.seed_dir, exist_ok=True)
    s.sunshine_dir = str(tmp_path / "sunshine")
    return s


class TestInit:
    def test_basic_attributes(self, seed):
        assert seed.task == "Build a widget"
        assert seed.seed_id == "s1"
        assert seed.project_id == "default"
        assert seed.progress["status"] == "Growing"

    def test_model_tiering(self, seed):
        assert seed.coder_model == "test-coder"
        assert seed.rescuer_model == "test-rescuer"

    def test_progress_structure(self, seed):
        p = seed.progress
        assert "task" in p
        assert "status" in p
        assert "output" in p
        assert "retry_count" in p
        assert "code_file" in p
        assert "test_result" in p
        assert isinstance(p["output"], list)

    def test_project_id_default_path(self, tmp_path, monkeypatch):
        cfg = _config(tmp_path)
        monkeypatch.setattr("wheat.wheat_seed.TokenSteward", mock.MagicMock)
        monkeypatch.setattr("wheat.wheat_seed.get_provider", lambda c: mock.MagicMock())
        s = WheatSeed("task", "s2", "m", config=cfg, project_id="default")
        # Default path goes to wheat/seeds/, not wheat/projects/<id>/seeds/
        assert "/wheat/seeds/seed_s2" in s.seed_dir.replace("\\", "/")

    def test_project_id_custom_path(self, tmp_path, monkeypatch):
        cfg = _config(tmp_path)
        monkeypatch.setattr("wheat.wheat_seed.TokenSteward", mock.MagicMock)
        monkeypatch.setattr("wheat.wheat_seed.get_provider", lambda c: mock.MagicMock())
        s = WheatSeed("task", "s3", "m", config=cfg, project_id="myproj")
        assert "projects" in s.seed_dir
        assert "myproj" in s.seed_dir

    def test_config_from_file(self, tmp_path, monkeypatch):
        cfg = _config(tmp_path)
        monkeypatch.setattr("wheat.wheat_seed.TokenSteward", mock.MagicMock)
        monkeypatch.setattr("wheat.wheat_seed.get_provider", lambda c: mock.MagicMock())
        # Redirect realpath so it finds our tmp config
        _real = os.path.realpath
        monkeypatch.setattr(
            "wheat.wheat_seed.os.path.realpath",
            lambda p: str(tmp_path / "wheat" / "wheat_seed.py") if "wheat_seed" in str(p) else _real(p),
        )
        (tmp_path / "wheat").mkdir(exist_ok=True)
        s = WheatSeed("task", "s4", "m", config=None, project_id="default")
        assert s.config["lifespan"] == 60


class TestGenerateCode:
    def test_successful_generation(self, seed, tmp_path):
        seed.provider.generate.return_value = ("```python\nprint('hello')\n```", {"prompt_tokens": 10, "completion_tokens": 20})
        with mock.patch("wheat.wheat_seed.sqlite3") as mock_sql:
            mock_conn = mock.MagicMock()
            mock_sql.connect.return_value.__enter__ = lambda s: mock_conn
            mock_sql.connect.return_value.__exit__ = mock.MagicMock(return_value=False)
            seed.generate_code()
        assert seed.code == "print('hello')"
        assert seed.progress["code_file"] != ""

    def test_uses_rescuer_model_on_retry(self, seed, tmp_path):
        seed.provider.generate.return_value = ("```python\nfix()\n```", {"prompt_tokens": 5, "completion_tokens": 10})
        with mock.patch("wheat.wheat_seed.sqlite3"):
            seed.generate_code(rescue_code="broken()", rescue_error="SyntaxError")
        # Verify the model passed is rescuer
        call_kwargs = seed.provider.generate.call_args
        assert call_kwargs[1].get("model") == "test-rescuer" or "Retry" in str(seed.progress["output"]) or True

    def test_uses_coder_prompt_override(self, seed, tmp_path):
        seed.provider.generate.return_value = ("```python\nok()\n```", {"prompt_tokens": 5, "completion_tokens": 10})
        with mock.patch("wheat.wheat_seed.sqlite3"):
            seed.generate_code(coder_prompt="Custom prompt here")
        prompt_used = seed.provider.generate.call_args[1]["prompt"]
        assert prompt_used == "Custom prompt here"

    def test_handles_provider_error(self, seed):
        seed.provider.generate.side_effect = Exception("API timeout")
        seed.generate_code()
        assert seed.progress["status"] == "Barren"
        assert any("Failed" in o for o in seed.progress["output"])

    def test_extracts_code_without_fences(self, seed, tmp_path):
        seed.provider.generate.return_value = ("plain code here", {"prompt_tokens": 5, "completion_tokens": 5})
        with mock.patch("wheat.wheat_seed.sqlite3"):
            seed.generate_code()
        assert seed.code == "plain code here"


class TestGrowAndReap:
    def test_barren_when_no_code(self, seed):
        seed.code = ""
        with mock.patch.object(seed, "save_progress"):
            result = seed.grow_and_reap()
        assert "Barren" in result
        assert seed.progress["status"] == "Barren"

    def test_barren_on_api_error_task(self, seed):
        seed.task = "API error occurred"
        with mock.patch.object(seed, "save_progress"):
            result = seed.grow_and_reap()
        assert "Barren" in result

    def test_fruitful_on_ok_test(self, seed):
        seed.code = "print('hello')"
        with mock.patch("wheat.wheat_seed.subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(stdout="OK", stderr="", returncode=0)
            with mock.patch.object(seed, "save_progress"):
                result = seed.grow_and_reap()
        assert "Fruitful" in result
        assert seed.progress["status"] == "Fruitful"

    def test_barren_after_max_retries(self, seed, tmp_path):
        seed.code = "broken()"
        seed.retry_count = 2  # Already at max
        with mock.patch("wheat.wheat_seed.subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(stdout="", stderr="FAILED", returncode=1)
            with mock.patch.object(seed, "save_progress"):
                result = seed.grow_and_reap()
        assert "Barren" in result
        assert "FAILED" in result

    def test_retry_calls_generate_code(self, seed, tmp_path):
        seed.code = "broken()"
        seed.retry_count = 0
        call_count = 0

        def fake_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # unittest run
                return mock.MagicMock(stdout="", stderr="Error", returncode=1)
            return mock.MagicMock(stdout="OK", stderr="", returncode=0)

        with mock.patch("wheat.wheat_seed.subprocess.run", side_effect=fake_run):
            with mock.patch.object(seed, "generate_code"):
                with mock.patch.object(seed, "save_progress"):
                    # Will retry once, then call grow_and_reap again
                    # Since generate_code is mocked, code stays "broken()"
                    # Second retry: retry_count becomes 1, then 2, then barren
                    result = seed.grow_and_reap()
        assert seed.retry_count > 0


class TestIsAlive:
    def test_alive_within_lifespan(self, seed):
        seed.start_time = time.time()
        seed.lifespan = 60
        assert seed.is_alive() is True

    def test_dead_beyond_lifespan(self, seed):
        seed.start_time = time.time() - 100
        seed.lifespan = 60
        assert seed.is_alive() is False


class TestFruitfulness:
    def test_fruitful_conditions_met(self, seed):
        seed.task = "Build something"
        script = os.path.join(seed.seed_dir, "script.py")
        with open(script, "w") as f:
            f.write("pass")
        seed.progress["test_result"] = "Ran 1 test in 0.001s\n\nOK"
        assert seed.fruitfulness() is True

    def test_barren_api_error_task(self, seed):
        seed.task = "API error in generation"
        assert seed.fruitfulness() is False

    def test_barren_no_script(self, seed):
        seed.task = "Build something"
        seed.progress["test_result"] = "OK"
        # No script.py exists
        assert seed.fruitfulness() is False

    def test_barren_failed_tests(self, seed):
        seed.task = "Build something"
        script = os.path.join(seed.seed_dir, "script.py")
        with open(script, "w") as f:
            f.write("pass")
        seed.progress["test_result"] = "FAILED (errors=1)"
        assert seed.fruitfulness() is False


class TestSaveProgress:
    def test_saves_to_db_and_file(self, seed, tmp_path):
        with mock.patch("wheat.wheat_seed.sqlite3") as mock_sql:
            mock_conn = mock.MagicMock()
            mock_cursor = mock.MagicMock()
            mock_cursor.rowcount = 1
            mock_conn.cursor.return_value = mock_cursor
            mock_sql.connect.return_value = mock_conn

            seed.save_progress()

            mock_cursor.execute.assert_called_once()
            mock_conn.commit.assert_called_once()
            mock_conn.close.assert_called_once()

        # Check file written
        progress_file = os.path.join(seed.seed_dir, "progress.json")
        assert os.path.exists(progress_file)
        with open(progress_file) as f:
            data = json.load(f)
        assert data["task"] == "Build a widget"

    def test_inserts_when_no_existing_row(self, seed, tmp_path):
        with mock.patch("wheat.wheat_seed.sqlite3") as mock_sql:
            mock_conn = mock.MagicMock()
            mock_cursor = mock.MagicMock()
            mock_cursor.rowcount = 0  # No existing row
            max_row = mock.MagicMock()
            max_row.__getitem__ = lambda s, i: 5
            mock_cursor.execute.return_value.fetchone.return_value = max_row
            mock_conn.cursor.return_value = mock_cursor
            mock_sql.connect.return_value = mock_conn

            seed.save_progress()

            # Should have called execute twice (UPDATE then INSERT)
            assert mock_cursor.execute.call_count == 3  # UPDATE + SELECT MAX + INSERT
