#wheat/token_steward.py
import json
import os
from datetime import datetime, timedelta

class TokenSteward:
    def __init__(self):
        config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "config.json")
        with open(config_path, "r") as f:
            config = json.load(f)
        self.period = config.get("token_period", "daily")
        self.file = "token_log.json"
        self.data = self._initialize_data()
        self.load_log()

    def _initialize_data(self):
        now = datetime.now()
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = period_start + timedelta(days=1)
        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }

    def load_log(self):
        if os.path.exists(self.file):
            try:
                with open(self.file, "r") as f:
                    loaded = json.load(f)
                period_end_str = loaded.get("period_end")
                if not isinstance(period_end_str, str):
                    print("Invalid period_end in token_log.json; resetting.")
                    self.data = self._initialize_data()
                    self.save_log()
                    return
                period_end = datetime.fromisoformat(period_end_str)
                if datetime.now() < period_end:
                    self.data = loaded
                else:
                    print("Daily period expired; resetting token counts.")
                    self.data = self._initialize_data()
                    self.save_log()
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error reading token_log.json ({e}); resetting.")
                self.data = self._initialize_data()
                self.save_log()
        else:
            self.save_log()

    def save_log(self):
        with open(self.file, "w") as f:
            json.dump(self.data, f)

    def can_water(self, tokens_needed, is_output=False):
        # Commented out for now—no limits enforced, just tracking
        # current_time = datetime.now()
        # period_end = datetime.fromisoformat(self.data["period_end"])
        # if current_time >= period_end:
        #     print("Daily period expired; resetting token counts.")
        #     self.data = self._initialize_data()
        #     self.save_log()
        # # For future autonomy: Check limits based on VCU-derived token caps
        # # e.g., if is_output: return self.data["completion_tokens"] + tokens_needed <= output_limit
        # return self.data["total_tokens"] + tokens_needed <= total_limit
        return True  # Always allow for now, tracking only

    def water_used(self, prompt_tokens, completion_tokens):
        current_time = datetime.now()
        period_end = datetime.fromisoformat(self.data["period_end"])
        if current_time >= period_end:
            print("Daily period expired; resetting token counts.")
            self.data = self._initialize_data()
        self.data["prompt_tokens"] += prompt_tokens
        self.data["completion_tokens"] += completion_tokens
        self.data["total_tokens"] += prompt_tokens + completion_tokens
        self.save_log()
        print(f"Tokens used: Prompt={self.data['prompt_tokens']}, Completion={self.data['completion_tokens']}, Total={self.data['total_tokens']} "
              f"(Period ends: {self.data['period_end']})")

if __name__ == "__main__":
    steward = TokenSteward()
    print(f"Initial state: {steward.data}")
    steward.water_used(500, 200)
    print(f"After using 500 prompt + 200 completion: {steward.data}")