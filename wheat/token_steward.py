#wheat/token_steward.py
import json
import os
from datetime import date

class TokenSteward:
    def __init__(self, daily_limit=100000):  # Increased limit for experimentation
        self.daily_limit = daily_limit
        self.file = "token_log.json"
        self.data = {"date": date.today().isoformat(), "tokens": 0}
        self.load_log()

    def load_log(self):
        if os.path.exists(self.file):
            with open(self.file, "r") as f:
                loaded = json.load(f)
                if date.today().isoformat() == loaded.get("date"):
                    self.data = loaded
                else:
                    self.data = {"date": date.today().isoformat(), "tokens": 0}
                    self.save_log()

    def save_log(self):
        with open(self.file, "w") as f:
            json.dump(self.data, f)

    def can_water(self, tokens_needed):
        return self.data["tokens"] + tokens_needed <= self.daily_limit

    def water_used(self, tokens):
        self.data["tokens"] += tokens
        self.save_log()
        print(f"Tokens used: {self.data['tokens']}/{self.daily_limit}")