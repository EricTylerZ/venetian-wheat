"""Tests for wheat/sower.py — seed planting and prompt formatting."""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _make_config(**overrides):
    """Minimal config dict for Sower construction."""
    base = {
        "llm_api": "venice",
        "max_tokens": 100,
        "timeout": 10,
        "seeds_per_run": 3,
        "strategist_prompt": "Generate {seeds_per_run} tasks. {stewards_map} {file_contents} Guidance: {guidance}",
        "coder_prompt": "Code: {task}",
        "models": {
            "strategist": "test-model",
            "coder": "test-coder",
        },
    }
    base.update(overrides)
    return base


# Patch TokenSteward so it never reads config.json from disk
@pytest.fixture(autouse=True)
def mock_token_steward(monkeypatch):
    mock_ts = MagicMock()
    mock_ts.can_water.return_value = True
    monkeypatch.setattr("wheat.sower.TokenSteward", lambda: mock_ts)
    return mock_ts


@pytest.fixture(autouse=True)
def mock_provider(monkeypatch):
    """Patch get_provider so Sower never hits a real API."""
    mock_prov = MagicMock()
    mock_prov.generate.return_value = ("task1\ntask2\ntask3", {"prompt_tokens": 10, "completion_tokens": 20})
    monkeypatch.setattr("wheat.sower.get_provider", lambda cfg: mock_prov)
    return mock_prov


# --- Sower init ---

class TestSowerInit:
    def test_init_with_config(self):
        from wheat.sower import Sower
        config = _make_config()
        s = Sower(config=config)
        assert s.llm_api == "venice"
        assert s.strategist_model == "test-model"
        assert s.coder_model == "test-coder"
        assert s.seeds_per_run == 3

    def test_init_claude_code_models(self):
        from wheat.sower import Sower
        config = _make_config(llm_api="claude_code", models={"strategist": "opus", "coder": "sonnet"})
        s = Sower(config=config)
        assert s.strategist_model == "opus"
        assert s.coder_model == "sonnet"

    def test_init_claude_code_no_models_uses_none(self):
        from wheat.sower import Sower
        config = _make_config(llm_api="claude_code", models={})
        s = Sower(config=config)
        assert s.strategist_model is None
        assert s.coder_model is None

    def test_init_venice_fallback_models(self):
        from wheat.sower import Sower
        config = _make_config(
            models={},
            default_strategist_model="fallback-strat",
            default_coder_model="fallback-coder",
        )
        s = Sower(config=config)
        assert s.strategist_model == "fallback-strat"
        assert s.coder_model == "fallback-coder"

    def test_init_venice_default_models(self):
        from wheat.sower import Sower
        config = _make_config(models={})
        s = Sower(config=config)
        assert s.strategist_model == "mistral-31-24b"
        assert s.coder_model == "mistral-31-24b"


# --- get_available_models ---

class TestGetAvailableModels:
    def test_claude_code_returns_hardcoded_list(self):
        from wheat.sower import Sower
        config = _make_config(llm_api="claude_code")
        s = Sower(config=config)
        models = s.get_available_models()
        assert len(models) == 3
        ids = [m["id"] for m in models]
        assert "opus" in ids
        assert "sonnet" in ids
        assert "haiku" in ids

    def test_venice_api_error_returns_empty(self):
        from wheat.sower import Sower
        config = _make_config(venice_models_url="http://fake")
        s = Sower(config=config)
        with patch("requests.get", side_effect=Exception("connection error")):
            models = s.get_available_models()
        assert models == []

    def test_venice_api_success(self):
        from wheat.sower import Sower
        config = _make_config(venice_models_url="http://fake")
        s = Sower(config=config)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": [{"id": "m1"}]}
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            models = s.get_available_models()
        assert models == [{"id": "m1"}]


# --- fetch_tasks ---

class TestFetchTasks:
    def test_fetch_tasks_parses_lines(self, mock_provider, mock_token_steward):
        from wheat.sower import Sower
        mock_provider.generate.return_value = ("alpha\nbeta\ngamma", {"prompt_tokens": 5, "completion_tokens": 10})
        s = Sower(config=_make_config())
        tasks = s.fetch_tasks("test prompt")
        assert tasks == ["alpha", "beta", "gamma"]
        mock_token_steward.water_used.assert_called_once_with(5, 10)

    def test_fetch_tasks_strips_blank_lines(self, mock_provider):
        from wheat.sower import Sower
        mock_provider.generate.return_value = ("alpha\n\n  \nbeta\n", {"prompt_tokens": 1, "completion_tokens": 1})
        s = Sower(config=_make_config())
        tasks = s.fetch_tasks("prompt")
        assert tasks == ["alpha", "beta"]

    def test_fetch_tasks_fallback_on_error(self, mock_provider):
        from wheat.sower import Sower
        mock_provider.generate.side_effect = Exception("API down")
        s = Sower(config=_make_config(seeds_per_run=2))
        tasks = s.fetch_tasks("prompt")
        assert len(tasks) == 2
        # Should be from _fallback_tasks
        assert "module" in tasks[0].lower() or "script" in tasks[0].lower() or "develop" in tasks[0].lower()


# --- _fallback_tasks ---

class TestFallbackTasks:
    def test_fallback_respects_seeds_per_run(self):
        from wheat.sower import Sower
        s = Sower(config=_make_config(seeds_per_run=2))
        tasks = s._fallback_tasks()
        assert len(tasks) == 2

    def test_fallback_returns_max_12(self):
        from wheat.sower import Sower
        s = Sower(config=_make_config(seeds_per_run=20))
        tasks = s._fallback_tasks()
        assert len(tasks) == 12  # only 12 defined


# --- sow_seeds ---

class TestSowSeeds:
    def test_sow_seeds_returns_correct_count(self, mock_provider):
        from wheat.sower import Sower
        mock_provider.generate.return_value = ("a\nb\nc", {"prompt_tokens": 1, "completion_tokens": 1})
        s = Sower(config=_make_config(seeds_per_run=3))
        tasks = s.sow_seeds(guidance="build stuff")
        assert len(tasks) == 3

    def test_sow_seeds_pads_with_fallback(self, mock_provider):
        from wheat.sower import Sower
        mock_provider.generate.return_value = ("only_one", {"prompt_tokens": 1, "completion_tokens": 1})
        s = Sower(config=_make_config(seeds_per_run=3))
        tasks = s.sow_seeds()
        assert len(tasks) == 3
        assert tasks[0] == "only_one"

    def test_sow_seeds_truncates_excess(self, mock_provider):
        from wheat.sower import Sower
        mock_provider.generate.return_value = ("a\nb\nc\nd\ne", {"prompt_tokens": 1, "completion_tokens": 1})
        s = Sower(config=_make_config(seeds_per_run=2))
        tasks = s.sow_seeds()
        assert len(tasks) == 2

    def test_sow_seeds_with_custom_strategist_prompt(self, mock_provider):
        from wheat.sower import Sower
        mock_provider.generate.return_value = ("x\ny", {"prompt_tokens": 1, "completion_tokens": 1})
        s = Sower(config=_make_config(seeds_per_run=2))
        tasks = s.sow_seeds(strategist_prompt="custom prompt here")
        assert len(tasks) == 2
        # verify the custom prompt was passed through
        call_args = mock_provider.generate.call_args
        assert call_args[1]["prompt"] == "custom prompt here" or call_args[0][0] == "custom prompt here"

    def test_sow_seeds_formats_default_prompt(self, mock_provider):
        from wheat.sower import Sower
        mock_provider.generate.return_value = ("a\nb\nc", {"prompt_tokens": 1, "completion_tokens": 1})
        config = _make_config(
            strategist_prompt="Seeds: {seeds_per_run} Map: {stewards_map} Files: {file_contents} Guide: {guidance}"
        )
        s = Sower(config=config)
        tasks = s.sow_seeds(guidance="plant wheat")
        call_args = mock_provider.generate.call_args
        prompt = call_args[1].get("prompt") or call_args[0][0]
        assert "Seeds: 3" in prompt
        assert "Guide: plant wheat" in prompt
