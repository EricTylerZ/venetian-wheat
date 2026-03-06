#wheat/sower.py
from dotenv import load_dotenv
import os
import json
from datetime import datetime
from wheat.token_steward import TokenSteward
from wheat.providers import get_provider

load_dotenv(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", ".env"))


class Sower:
    def __init__(self, config=None):
        self.token_steward = TokenSteward()
        if config is None:
            with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "config.json"), "r") as f:
                config = json.load(f)
        self.config = config
        self.llm_api = config.get("llm_api", "venice")

        # Model tiering: use models dict if available, fall back to legacy keys
        models = config.get("models", {})
        self.strategist_model = models.get("strategist", config.get("default_strategist_model", "mistral-31-24b"))
        self.coder_model = models.get("coder", config.get("default_coder_model", "mistral-31-24b"))

        self.max_tokens = config["max_tokens"]
        self.timeout = config["timeout"]
        self.seeds_per_run = config.get("seeds_per_run", 3)
        self.strategist_prompt = config["strategist_prompt"]
        self.provider = get_provider(config)

    def get_available_models(self):
        if self.llm_api == "claude_code":
            return [{"id": "opus", "name": "Claude Opus"}, {"id": "sonnet", "name": "Claude Sonnet"}, {"id": "haiku", "name": "Claude Haiku"}]
        api_key = os.environ.get("VENICE_API_KEY") or "MISSING_KEY"
        models_url = self.config.get(f"{self.llm_api}_models_url", self.config.get("venice_models_url"))
        import requests
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        try:
            response = requests.get(models_url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json().get("data", [])
        except Exception:
            return []

    def fetch_tasks(self, prompt):
        sunshine_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "logs", "sunshine")
        try:
            text, usage = self.provider.generate(
                prompt=prompt,
                model=self.strategist_model,
                max_tokens=self.max_tokens,
                sunshine_dir=sunshine_dir,
            )
            self.token_steward.water_used(usage["prompt_tokens"], usage["completion_tokens"])
            tasks = [t.strip() for t in text.strip().split("\n") if t.strip()]
            return tasks
        except Exception as e:
            print(f"Sower failed: {str(e)[:200]}")
            return self._fallback_tasks()

    def _fallback_tasks(self):
        return [
            "Develop a module to monitor system resources",
            "Create a script to log token usage trends",
            "Add a unittest suite for token management",
            "Implement a retry mechanism for large API calls",
            "Build a caching system for strategist responses",
            "Refactor sower.py for modular task generation",
            "Write a scheduler for background task execution",
            "Create a notification system for token limits",
            "Develop a helper for parsing large API outputs",
            "Implement a seed validator for complex scripts",
            "Analyze API response times for optimization",
            "Visualize seed success rates over time"
        ][:self.seeds_per_run]

    def sow_seeds(self, guidance=None, strategist_prompt=None):
        log_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "logs", "runs")
        latest_log = max([os.path.join(log_dir, f) for f in os.listdir(log_dir) if f.startswith("run_")] or [], default=None, key=os.path.getmtime) if os.path.exists(log_dir) else None
        log_content = open(latest_log, "r", encoding="utf-8").read() if latest_log else ""
        prompt = strategist_prompt if strategist_prompt else self.strategist_prompt.format(
            stewards_map="", file_contents="", seeds_per_run=self.seeds_per_run, guidance=guidance or "No user input—sow tasks to improve wheat seeds."
        )
        tasks = self.fetch_tasks(prompt)
        while len(tasks) < self.seeds_per_run:
            tasks.extend(self._fallback_tasks()[:self.seeds_per_run - len(tasks)])
        return tasks[:self.seeds_per_run]
