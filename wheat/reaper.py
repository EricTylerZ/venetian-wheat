#wheat/reaper.py
import re
from wheat.wheat_seed import WheatSeed


# Reseed strategies keyed by detected category in the original task.
# Each entry maps a keyword pattern to a list of meaningful follow-up directions.
RESEED_STRATEGIES = {
    r"monitor|resource|system": [
        "Add alerting thresholds and notification hooks",
        "Persist historical metrics to SQLite for trend analysis",
        "Add configurable sampling intervals",
    ],
    r"log|token|usage": [
        "Visualize usage trends with ASCII sparklines",
        "Add CSV/JSON export for external dashboards",
        "Detect anomalous spikes and flag them",
    ],
    r"test|unittest|suite": [
        "Add edge-case and boundary-value tests",
        "Add integration tests that hit the real API with mocked responses",
        "Measure and report code coverage percentage",
    ],
    r"retry|resilien|backoff": [
        "Add circuit-breaker pattern to avoid hammering a down API",
        "Make retry strategy configurable via config.json",
        "Add jitter and exponential backoff cap",
    ],
    r"cache|caching": [
        "Add TTL-based cache expiration",
        "Add cache size limits with LRU eviction",
        "Persist cache to disk across restarts",
    ],
    r"schedul|task|queue": [
        "Add priority-based task ordering",
        "Add concurrency limits per task type",
        "Add dead-letter handling for repeatedly failing tasks",
    ],
    r"api|request|response": [
        "Add request/response schema validation",
        "Add latency tracking and timeout tuning",
        "Support streaming responses for long generations",
    ],
    r"parse|extract|output": [
        "Handle additional output formats (YAML, TOML)",
        "Add structured error extraction from LLM responses",
        "Add confidence scoring for extracted content",
    ],
}

# Generic follow-ups when no category matches
GENERIC_STRATEGIES = [
    "Add comprehensive error handling and edge-case coverage",
    "Extract reusable utilities into wheat/helpers/",
    "Add input validation and type checking",
    "Write integration tests against the rest of the system",
]


class Reaper:
    def evaluate(self, seed):
        status = "fruitful" if seed.fruitfulness() else "barren"
        return f"Seed {seed.seed_id} {status}: {seed.task}"

    def _pick_follow_up(self, task):
        """Choose a meaningful follow-up direction based on what the seed actually did."""
        task_lower = task.lower()
        for pattern, strategies in RESEED_STRATEGIES.items():
            if re.search(pattern, task_lower):
                # Pick a strategy that isn't just repeating words from the original task
                for strategy in strategies:
                    if strategy.lower() not in task_lower:
                        return strategy
                return strategies[0]
        return GENERIC_STRATEGIES[hash(task) % len(GENERIC_STRATEGIES)]

    def reseed(self, seed):
        if not seed.fruitfulness():
            return None

        follow_up = self._pick_follow_up(seed.task)

        # Build a new task that references what succeeded and pushes further
        # Strip any previous "then ..." chain to avoid infinite growth
        base_task = seed.task.split(" then ")[0].strip()
        new_task = f"{base_task} then {follow_up.lower()}"

        return WheatSeed(new_task, seed.seed_id + "_1", seed.coder_model)
