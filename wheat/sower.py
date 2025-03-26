#wheat/sower.py
from dotenv import load_dotenv
import requests
import os
import json
from datetime import datetime
from wheat.token_steward import TokenSteward

load_dotenv(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", ".env"))

class Sower:
    def __init__(self):
        self.token_steward = TokenSteward()
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "config.json"), "r") as f:
            config = json.load(f)
        self.llm_api = config.get("llm_api", "venice")
        self.api_url = config.get(f"{self.llm_api}_api_url", config["venice_api_url"])
        self.models_url = config.get(f"{self.llm_api}_models_url", config["venice_models_url"])
        self.max_tokens = config["max_tokens"]
        self.timeout = config["timeout"]
        self.strategist_model = config["default_strategist_model"]
        self.coder_model = config["default_coder_model"]
        self.seeds_per_run = config.get("seeds_per_run", 3)  # Already seeds_per_run
        self.strategist_prompt = config["strategist_prompt"].format(seeds_per_run=self.seeds_per_run)
        self.api_key = os.environ.get("VENICE_API_KEY") or "MISSING_KEY"

    def get_available_models(self):
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            response = requests.get(self.models_url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json().get("data", [])
        except requests.RequestException:
            return []

    def select_model(self, trait=None):
        models = self.get_available_models()
        if not models:
            return self.strategist_model
        if trait:
            for model in models:
                if trait in model.get("traits", []):
                    return model.get("id")
        for model in models:
            if model.get("id") == self.strategist_model:
                return self.strategist_model
        return models[0].get("id")

    def fetch_tasks(self, prompt):
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.strategist_model,
            "messages": [{"role": "system", "content": prompt}],
            "max_tokens": self.max_tokens
        }
        tokens_estimate = len(prompt) // 4 + self.max_tokens
        sunshine_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "logs", "sunshine")
        os.makedirs(sunshine_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        with open(os.path.join(sunshine_dir, f"{timestamp}_{self.llm_api}_request.json"), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=self.timeout)
            response.raise_for_status()
            raw_response = response.json()
            prompt_tokens = raw_response.get("usage", {}).get("prompt_tokens", tokens_estimate)
            completion_tokens = raw_response.get("usage", {}).get("completion_tokens", 0)
            self.token_steward.water_used(prompt_tokens, completion_tokens)
            with open(os.path.join(sunshine_dir, f"{timestamp}_{self.llm_api}_{response.status_code}.json"), "w", encoding="utf-8") as f:
                json.dump(raw_response, f, indent=2)
            tasks = [t.strip() for t in raw_response["choices"][0]["message"]["content"].strip().split("\n") if t.strip()]
            return tasks
        except requests.RequestException as e:
            error_msg = f"API error: {str(e)} - Key: {self.api_key[:4]}..."
            print(f"Sower failed: {error_msg}")
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
            "Implement a seed validator for complex scripts",  # Updated "strain" to "seed"
            "Analyze API response times for optimization",
            "Visualize seed success rates over time"  # Updated "strain" to "seed"
        ][:self.seeds_per_run]

    def sow_seeds(self, guidance=None):
        log_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "logs", "runs")
        latest_log = max([os.path.join(log_dir, f) for f in os.listdir(log_dir) if f.startswith("run_")] or [], default=None, key=os.path.getmtime) if os.path.exists(log_dir) else None
        log_content = open(latest_log, "r", encoding="utf-8").read() if latest_log else ""
        prompt = self.strategist_prompt + f"\nField log: {log_content[:1000]}\n" + (f"User input: {guidance}" if guidance else "No user input—sow tasks to improve wheat seeds.")  # Updated "strains" to "seeds"
        tasks = self.fetch_tasks(prompt)
        while len(tasks) < self.seeds_per_run:
            tasks.extend(self._fallback_tasks()[:self.seeds_per_run - len(tasks)])
        return tasks[:self.seeds_per_run]