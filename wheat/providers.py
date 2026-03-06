# wheat/providers.py
"""
LLM provider abstraction. Supports:
  - "venice" / "grok": OpenAI-compatible chat completions APIs (requires API key)
  - "claude_code": Claude Code CLI (uses Pro Max subscription, no API fees)

Each provider implements generate(prompt, model, max_tokens) -> (text, usage_dict)
"""
import json
import os
import subprocess
import tempfile
import time
import random
import requests
from datetime import datetime


class APIProvider:
    """Venice / Grok / any OpenAI-compatible endpoint."""

    def __init__(self, api_url, api_key, timeout=150):
        self.api_url = api_url
        self.api_key = api_key
        self.timeout = timeout

    def generate(self, prompt, model, max_tokens=4096, retries=3, sunshine_dir=None):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": prompt}],
            "max_tokens": max_tokens,
        }

        # Log request if sunshine_dir provided
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        if sunshine_dir:
            os.makedirs(sunshine_dir, exist_ok=True)
            with open(os.path.join(sunshine_dir, f"{timestamp}_request.json"), "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

        last_error = None
        for attempt in range(retries):
            try:
                response = requests.post(
                    self.api_url, headers=headers, json=payload, timeout=self.timeout
                )
                response.raise_for_status()
                data = response.json()

                # Log response
                if sunshine_dir:
                    with open(os.path.join(sunshine_dir, f"{timestamp}_response.json"), "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)

                text = data["choices"][0]["message"]["content"].strip()
                usage = data.get("usage", {})
                return text, {
                    "prompt_tokens": usage.get("prompt_tokens", len(prompt) // 4),
                    "completion_tokens": usage.get("completion_tokens", 0),
                }
            except requests.RequestException as e:
                last_error = e
                if sunshine_dir:
                    with open(os.path.join(sunshine_dir, f"{timestamp}_error_{attempt}.json"), "w", encoding="utf-8") as f:
                        json.dump({"error": str(e)[:500]}, f, indent=2)
                if attempt < retries - 1:
                    time.sleep(2 ** attempt + random.uniform(0, 1))
        raise last_error


class ClaudeCodeProvider:
    """
    Uses the Claude Code CLI (`claude`) which is included with Pro Max.
    No API key needed — it uses your authenticated CLI session.

    Requirements:
      - `claude` CLI installed and authenticated (claude login)
      - Pro Max subscription active

    This shells out to `claude -p <prompt>` for non-interactive single-shot
    generation, which is the cleanest way to use it programmatically.
    """

    def __init__(self, timeout=300, model=None):
        self.timeout = timeout
        self.model = model  # e.g. "opus", "sonnet" — None uses CLI default

    def generate(self, prompt, model=None, max_tokens=None, retries=2, sunshine_dir=None):
        model = model or self.model
        last_error = None

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        if sunshine_dir:
            os.makedirs(sunshine_dir, exist_ok=True)
            with open(os.path.join(sunshine_dir, f"{timestamp}_claude_request.json"), "w", encoding="utf-8") as f:
                json.dump({"model": model, "prompt_length": len(prompt), "prompt_preview": prompt[:500]}, f, indent=2)

        for attempt in range(retries):
            prompt_file = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", delete=False, encoding="utf-8"
                ) as f:
                    f.write(prompt)
                    prompt_file = f.name

                cmd = ["claude", "-p"]
                if model:
                    cmd.extend(["--model", model])
                with open(prompt_file, "r", encoding="utf-8") as pf:
                    result = subprocess.run(
                        cmd,
                        stdin=pf,
                        capture_output=True,
                        text=True,
                        timeout=self.timeout,
                    )

                if result.returncode != 0:
                    raise RuntimeError(
                        f"claude CLI exited {result.returncode}: {result.stderr[:200]}"
                    )

                text = result.stdout.strip()

                if sunshine_dir:
                    with open(os.path.join(sunshine_dir, f"{timestamp}_claude_response.json"), "w", encoding="utf-8") as f:
                        json.dump({"model": model, "response_length": len(text), "response_preview": text[:500]}, f, indent=2)

                return text, {
                    "prompt_tokens": len(prompt) // 4,
                    "completion_tokens": len(text) // 4,
                }

            except (subprocess.TimeoutExpired, RuntimeError, FileNotFoundError) as e:
                last_error = e
                if sunshine_dir:
                    with open(os.path.join(sunshine_dir, f"{timestamp}_claude_error_{attempt}.json"), "w", encoding="utf-8") as f:
                        json.dump({"error": str(e)[:500]}, f, indent=2)
                if attempt < retries - 1:
                    time.sleep(2 ** attempt + random.uniform(0, 1))
            finally:
                if prompt_file and os.path.exists(prompt_file):
                    os.unlink(prompt_file)

        raise last_error


def get_provider(config):
    """
    Factory: returns the right provider based on config["llm_api"].

    Supports:
      "venice" / "grok" — OpenAI-compatible API (needs API key)
      "claude_code"     — Claude Code CLI (Pro Max, no API fees)
    """
    api_type = config.get("llm_api", "venice")

    if api_type == "claude_code":
        return ClaudeCodeProvider(
            timeout=config.get("claude_code_timeout", 300),
            model=config.get("models", {}).get("coder"),
        )

    # Venice, Grok, or any OpenAI-compatible API
    api_url = config.get(f"{api_type}_api_url", config.get("venice_api_url"))
    api_key = os.environ.get("VENICE_API_KEY") or "MISSING_KEY"
    return APIProvider(
        api_url=api_url,
        api_key=api_key,
        timeout=config.get("timeout", 150),
    )
