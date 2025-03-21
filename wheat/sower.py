#wheat/sower.py
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
import requests
import os
import json

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

class Sower:
    def __init__(self):
        with open(os.path.join(os.path.dirname(__file__), "config.json"), "r") as f:
            config = json.load(f)
        self.api_url = config["venice_api_url"]
        self.models_url = config["venice_models_url"]
        self.max_tokens = config["max_tokens"]
        self.timeout = config["timeout"]
        self.strategist_model = config["default_strategist_model"]
        self.coder_model = config["default_coder_model"]
        self.strategist_prompt = config["strategist_prompt"]
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
        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=self.timeout)
            response.raise_for_status()
            tasks = [t.strip() for t in response.json()["choices"][0]["message"]["content"].strip().split("\n") if t.strip()]
            return tasks
        except requests.RequestException as e:
            return [f"API error: {str(e)} - Key: {self.api_key[:4]}..."]

    def sow_seeds(self, guidance=None):
        log_path = os.path.join(os.path.dirname(__file__), "field_log.txt")
        log_content = open(log_path, "r").read() if os.path.exists(log_path) else ""
        prompt = self.strategist_prompt + f"\nField log: {log_content[:1000]}\n" + (f"User input: {guidance}" if guidance else "No user input—sow tasks to improve wheat strains.")
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.fetch_tasks, prompt)
            return future.result()

if __name__ == "__main__":
    sower = Sower()
    tasks = sower.sow_seeds("Focus on improving existing wheat files.")
    for task in tasks:
        print(task)