#wheat/token_steward.py
import json
import os
from datetime import datetime, timedelta

class TokenSteward:
    def __init__(self):
        # Load config
        config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "config.json")
        with open(config_path, "r") as f:
            config = json.load(f)
        self.limit = config.get("token_limit", 100000)  # Default to 100k if not specified
        self.period = config.get("token_period", "daily")  # "hourly" or "daily"
        self.file = "token_log.json"
        self.data = self._initialize_data()
        self.load_log()

    def _initialize_data(self):
        """Initialize token data based on period."""
        now = datetime.now()
        if self.period == "hourly":
            period_start = now.replace(minute=0, second=0, microsecond=0)
            period_end = period_start + timedelta(hours=1)
        else:  # Default to daily
            period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            period_end = period_start + timedelta(days=1)
        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "tokens": 0
        }

    def load_log(self):
        """Load token usage from file and reset if period has expired or file is invalid."""
        if os.path.exists(self.file):
            try:
                with open(self.file, "r") as f:
                    loaded = json.load(f)
                period_end_str = loaded.get("period_end")
                if not isinstance(period_end_str, str):  # Handle None or invalid type
                    print("Invalid period_end in token_log.json; resetting.")
                    self.data = self._initialize_data()
                    self.save_log()
                    return
                period_end = datetime.fromisoformat(period_end_str)
                if datetime.now() < period_end:  # Period still active
                    self.data = loaded
                else:  # Period expired, reset
                    self.data = self._initialize_data()
                    self.save_log()
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error reading token_log.json ({e}); resetting.")
                self.data = self._initialize_data()
                self.save_log()
        else:
            self.save_log()  # Create new log if none exists

    def save_log(self):
        """Save current token usage to file."""
        with open(self.file, "w") as f:
            json.dump(self.data, f)

    def can_water(self, tokens_needed):
        """Check if adding tokens exceeds the limit."""
        current_time = datetime.now()
        period_end = datetime.fromisoformat(self.data["period_end"])
        if current_time >= period_end:  # Reset if period has ended
            self.data = self._initialize_data()
            self.save_log()
        return self.data["tokens"] + tokens_needed <= self.limit

    def water_used(self, tokens):
        """Log tokens used and update the file."""
        current_time = datetime.now()
        period_end = datetime.fromisoformat(self.data["period_end"])
        if current_time >= period_end:  # Reset if period has ended
            self.data = self._initialize_data()
        self.data["tokens"] += tokens
        self.save_log()
        print(f"Tokens used: {self.data['tokens']}/{self.limit} (Period ends: {self.data['period_end']})")

if __name__ == "__main__":
    steward = TokenSteward()
    print(f"Initial state: {steward.data}")
    print(f"Can use 1000 tokens? {steward.can_water(1000)}")
    steward.water_used(1000)
    print(f"After using 1000 tokens: {steward.data}")