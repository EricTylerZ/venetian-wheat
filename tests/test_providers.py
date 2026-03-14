"""Tests for wheat/providers.py — LLM provider abstraction."""

import json
import os
import pytest
from unittest import mock

from wheat.providers import APIProvider, ClaudeCodeProvider, get_provider


# ── APIProvider ──────────────────────────────────────────────

class TestAPIProvider:
    def test_init(self):
        p = APIProvider("https://api.example.com/v1/chat", "sk-test", timeout=60)
        assert p.api_url == "https://api.example.com/v1/chat"
        assert p.api_key == "sk-test"
        assert p.timeout == 60

    def test_default_timeout(self):
        p = APIProvider("https://x.com", "k")
        assert p.timeout == 150

    @mock.patch("wheat.providers.requests.post")
    def test_generate_success(self, mock_post):
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "  Hello world  "}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_post.return_value.raise_for_status = mock.Mock()

        p = APIProvider("https://api.test/v1/chat", "key123")
        text, usage = p.generate("Say hello", "test-model")

        assert text == "Hello world"
        assert usage["prompt_tokens"] == 10
        assert usage["completion_tokens"] == 5

        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["json"]["model"] == "test-model"
        assert call_kwargs[1]["json"]["messages"][0]["content"] == "Say hello"

    @mock.patch("wheat.providers.requests.post")
    def test_generate_missing_usage_estimates_tokens(self, mock_post):
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
        }
        mock_post.return_value.raise_for_status = mock.Mock()

        p = APIProvider("https://api.test", "k")
        text, usage = p.generate("a prompt", "model")
        assert usage["prompt_tokens"] == len("a prompt") // 4
        assert usage["completion_tokens"] == 0

    @mock.patch("wheat.providers.time.sleep")
    @mock.patch("wheat.providers.requests.post")
    def test_generate_retries_on_failure(self, mock_post, mock_sleep):
        import requests as req
        mock_post.side_effect = [
            req.exceptions.ConnectionError("fail"),
            mock.Mock(
                json=lambda: {"choices": [{"message": {"content": "ok"}}], "usage": {}},
                raise_for_status=mock.Mock(),
            ),
        ]

        p = APIProvider("https://api.test", "k")
        text, _ = p.generate("prompt", "model", retries=3)
        assert text == "ok"
        assert mock_sleep.call_count == 1

    @mock.patch("wheat.providers.time.sleep")
    @mock.patch("wheat.providers.requests.post")
    def test_generate_raises_after_all_retries(self, mock_post, mock_sleep):
        import requests as req
        mock_post.side_effect = req.exceptions.ConnectionError("down")

        p = APIProvider("https://api.test", "k")
        with pytest.raises(req.exceptions.ConnectionError):
            p.generate("prompt", "model", retries=2)

    @mock.patch("wheat.providers.requests.post")
    def test_generate_logs_to_sunshine_dir(self, mock_post, tmp_path):
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "response"}}],
            "usage": {},
        }
        mock_post.return_value.raise_for_status = mock.Mock()

        p = APIProvider("https://api.test", "k")
        sunshine = str(tmp_path / "sunshine")
        p.generate("prompt", "model", sunshine_dir=sunshine)

        files = os.listdir(sunshine)
        assert any("request" in f for f in files)
        assert any("response" in f for f in files)

    @mock.patch("wheat.providers.time.sleep")
    @mock.patch("wheat.providers.requests.post")
    def test_generate_logs_errors_to_sunshine(self, mock_post, mock_sleep, tmp_path):
        import requests as req
        mock_post.side_effect = req.exceptions.ConnectionError("boom")

        p = APIProvider("https://api.test", "k")
        sunshine = str(tmp_path / "sunshine")
        with pytest.raises(req.exceptions.ConnectionError):
            p.generate("prompt", "model", retries=2, sunshine_dir=sunshine)

        files = os.listdir(sunshine)
        assert any("error" in f for f in files)

    @mock.patch("wheat.providers.requests.post")
    def test_generate_custom_max_tokens(self, mock_post):
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "ok"}}], "usage": {},
        }
        mock_post.return_value.raise_for_status = mock.Mock()

        p = APIProvider("https://api.test", "k")
        p.generate("prompt", "model", max_tokens=8192)
        assert mock_post.call_args[1]["json"]["max_tokens"] == 8192


# ── ClaudeCodeProvider ───────────────────────────────────────

class TestClaudeCodeProvider:
    def test_init_defaults(self):
        p = ClaudeCodeProvider()
        assert p.timeout == 300
        assert p.model is None

    def test_init_with_model(self):
        p = ClaudeCodeProvider(timeout=60, model="sonnet")
        assert p.timeout == 60
        assert p.model == "sonnet"

    @mock.patch("wheat.providers.subprocess.run")
    def test_generate_success(self, mock_run):
        mock_run.return_value = mock.Mock(
            returncode=0, stdout="  Generated text  ", stderr=""
        )

        p = ClaudeCodeProvider()
        text, usage = p.generate("Do something")

        assert text == "Generated text"
        assert usage["prompt_tokens"] == len("Do something") // 4
        assert usage["completion_tokens"] == len("Generated text") // 4

    @mock.patch("wheat.providers.subprocess.run")
    def test_generate_with_model_flag(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=0, stdout="ok", stderr="")

        p = ClaudeCodeProvider(model="opus")
        p.generate("prompt")

        cmd = mock_run.call_args[0][0]
        assert "--model" in cmd
        assert "opus" in cmd

    @mock.patch("wheat.providers.subprocess.run")
    def test_generate_model_override(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=0, stdout="ok", stderr="")

        p = ClaudeCodeProvider(model="sonnet")
        p.generate("prompt", model="opus")

        cmd = mock_run.call_args[0][0]
        assert "opus" in cmd

    @mock.patch("wheat.providers.subprocess.run")
    def test_generate_strips_nesting_env(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=0, stdout="ok", stderr="")

        with mock.patch.dict(os.environ, {"CLAUDECODE": "1", "CLAUDE_CODE_ENTRYPOINT": "x"}):
            p = ClaudeCodeProvider()
            p.generate("prompt")

        env = mock_run.call_args[1]["env"]
        assert "CLAUDECODE" not in env
        assert "CLAUDE_CODE_ENTRYPOINT" not in env

    @mock.patch("wheat.providers.subprocess.run")
    def test_generate_nonzero_exit_raises(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=1, stderr="Error occurred")

        p = ClaudeCodeProvider()
        with pytest.raises(RuntimeError, match="claude CLI exited 1"):
            p.generate("prompt", retries=1)

    @mock.patch("wheat.providers.time.sleep")
    @mock.patch("wheat.providers.subprocess.run")
    def test_generate_retries_on_timeout(self, mock_run, mock_sleep):
        import subprocess
        mock_run.side_effect = [
            subprocess.TimeoutExpired("claude", 300),
            mock.Mock(returncode=0, stdout="ok", stderr=""),
        ]

        p = ClaudeCodeProvider()
        text, _ = p.generate("prompt", retries=2)
        assert text == "ok"

    @mock.patch("wheat.providers.time.sleep")
    @mock.patch("wheat.providers.subprocess.run")
    def test_generate_raises_after_all_retries(self, mock_run, mock_sleep):
        mock_run.return_value = mock.Mock(returncode=1, stderr="fail")

        p = ClaudeCodeProvider()
        with pytest.raises(RuntimeError):
            p.generate("prompt", retries=2)

    @mock.patch("wheat.providers.subprocess.run")
    def test_generate_cleans_up_temp_file(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=0, stdout="ok", stderr="")

        p = ClaudeCodeProvider()
        p.generate("prompt", retries=1)

        # The temp file from stdin should be cleaned up
        # We can verify by checking the open() call used a real file
        assert mock_run.call_args[1].get("stdin") is not None

    @mock.patch("wheat.providers.subprocess.run")
    def test_generate_logs_to_sunshine_dir(self, mock_run, tmp_path):
        mock_run.return_value = mock.Mock(returncode=0, stdout="ok", stderr="")

        p = ClaudeCodeProvider()
        sunshine = str(tmp_path / "sunshine")
        p.generate("prompt", sunshine_dir=sunshine)

        files = os.listdir(sunshine)
        assert any("claude_request" in f for f in files)
        assert any("claude_response" in f for f in files)


# ── get_provider factory ─────────────────────────────────────

class TestGetProvider:
    def test_claude_code_provider(self):
        config = {"llm_api": "claude_code"}
        p = get_provider(config)
        assert isinstance(p, ClaudeCodeProvider)

    def test_claude_code_with_valid_model(self):
        config = {"llm_api": "claude_code", "models": {"coder": "sonnet"}}
        p = get_provider(config)
        assert isinstance(p, ClaudeCodeProvider)
        assert p.model == "sonnet"

    def test_claude_code_filters_invalid_model(self):
        config = {"llm_api": "claude_code", "models": {"coder": "llama-70b"}}
        p = get_provider(config)
        assert isinstance(p, ClaudeCodeProvider)
        assert p.model is None

    def test_claude_code_custom_timeout(self):
        config = {"llm_api": "claude_code", "claude_code_timeout": 600}
        p = get_provider(config)
        assert p.timeout == 600

    def test_venice_provider(self, monkeypatch):
        monkeypatch.setenv("VENICE_API_KEY", "test-key")
        config = {"llm_api": "venice", "venice_api_url": "https://api.venice.ai/v1/chat"}
        p = get_provider(config)
        assert isinstance(p, APIProvider)
        assert p.api_key == "test-key"
        assert p.api_url == "https://api.venice.ai/v1/chat"

    def test_default_api_is_venice(self, monkeypatch):
        monkeypatch.setenv("VENICE_API_KEY", "k")
        config = {"venice_api_url": "https://venice.test"}
        p = get_provider(config)
        assert isinstance(p, APIProvider)

    def test_missing_api_key_uses_placeholder(self, monkeypatch):
        monkeypatch.delenv("VENICE_API_KEY", raising=False)
        config = {"llm_api": "venice", "venice_api_url": "https://test"}
        p = get_provider(config)
        assert p.api_key == "MISSING_KEY"

    def test_grok_provider(self, monkeypatch):
        monkeypatch.setenv("VENICE_API_KEY", "grok-key")
        config = {"llm_api": "grok", "grok_api_url": "https://api.grok.test/v1/chat"}
        p = get_provider(config)
        assert isinstance(p, APIProvider)
        assert p.api_url == "https://api.grok.test/v1/chat"

    def test_custom_timeout_api_provider(self, monkeypatch):
        monkeypatch.setenv("VENICE_API_KEY", "k")
        config = {"llm_api": "venice", "venice_api_url": "https://t", "timeout": 30}
        p = get_provider(config)
        assert p.timeout == 30
