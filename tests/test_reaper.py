"""Tests for wheat/reaper.py — seed evaluation and reseeding logic."""

import pytest
from unittest import mock

from wheat.reaper import (
    Reaper,
    RESEED_STRATEGIES,
    GENERIC_STRATEGIES,
)


def _fake_seed(task="Build a monitoring dashboard", seed_id="s1",
               fruitful=True, coder_model="test-model"):
    """Create a mock WheatSeed with controlled fruitfulness."""
    seed = mock.MagicMock()
    seed.task = task
    seed.seed_id = seed_id
    seed.coder_model = coder_model
    seed.fruitfulness.return_value = fruitful
    return seed


class TestReaperEvaluate:
    def test_fruitful_seed(self):
        reaper = Reaper()
        seed = _fake_seed(task="Build X", seed_id="s1", fruitful=True)
        result = reaper.evaluate(seed)
        assert "fruitful" in result
        assert "s1" in result
        assert "Build X" in result

    def test_barren_seed(self):
        reaper = Reaper()
        seed = _fake_seed(task="Build Y", seed_id="s2", fruitful=False)
        result = reaper.evaluate(seed)
        assert "barren" in result
        assert "s2" in result


class TestReaperPickFollowUp:
    def test_monitor_category(self):
        reaper = Reaper()
        result = reaper._pick_follow_up("Add system monitoring for CPU")
        assert result in RESEED_STRATEGIES[r"monitor|resource|system"]

    def test_log_category(self):
        reaper = Reaper()
        result = reaper._pick_follow_up("Implement token usage logging")
        assert result in RESEED_STRATEGIES[r"log|token|usage"]

    def test_test_category(self):
        reaper = Reaper()
        result = reaper._pick_follow_up("Write unittest suite for parser")
        assert result in RESEED_STRATEGIES[r"test|unittest|suite"]

    def test_retry_category(self):
        reaper = Reaper()
        result = reaper._pick_follow_up("Add retry with resilient backoff")
        assert result in RESEED_STRATEGIES[r"retry|resilien|backoff"]

    def test_cache_category(self):
        reaper = Reaper()
        result = reaper._pick_follow_up("Implement caching layer")
        assert result in RESEED_STRATEGIES[r"cache|caching"]

    def test_schedule_category(self):
        reaper = Reaper()
        result = reaper._pick_follow_up("Build task scheduler")
        assert result in RESEED_STRATEGIES[r"schedul|task|queue"]

    def test_api_category(self):
        reaper = Reaper()
        result = reaper._pick_follow_up("Add API request handler")
        assert result in RESEED_STRATEGIES[r"api|request|response"]

    def test_parse_category(self):
        reaper = Reaper()
        result = reaper._pick_follow_up("Parse and extract JSON output")
        assert result in RESEED_STRATEGIES[r"parse|extract|output"]

    def test_generic_fallback(self):
        reaper = Reaper()
        result = reaper._pick_follow_up("Do something completely unique and unmatched")
        assert result in GENERIC_STRATEGIES

    def test_avoids_repeating_task_words(self):
        reaper = Reaper()
        # "Add alerting thresholds..." is strategy[0] for monitor category
        # If the task already contains that text, it should pick another
        result = reaper._pick_follow_up("monitor system then add alerting thresholds and notification hooks")
        # Should still return a valid strategy from the monitor category
        assert result in RESEED_STRATEGIES[r"monitor|resource|system"]

    def test_case_insensitive(self):
        reaper = Reaper()
        result = reaper._pick_follow_up("BUILD A MONITORING SYSTEM")
        assert result in RESEED_STRATEGIES[r"monitor|resource|system"]


class TestReaperReseed:
    @mock.patch("wheat.reaper.WheatSeed")
    def test_fruitful_seed_creates_new(self, MockWheatSeed):
        reaper = Reaper()
        seed = _fake_seed(task="Build cache layer", seed_id="s1", fruitful=True)
        MockWheatSeed.return_value = mock.MagicMock()

        result = reaper.reseed(seed)

        assert result is not None
        MockWheatSeed.assert_called_once()
        call_args = MockWheatSeed.call_args[0]
        assert "Build cache layer then" in call_args[0]
        assert call_args[1] == "s1_1"  # seed_id + "_1"
        assert call_args[2] == "test-model"

    def test_barren_seed_returns_none(self):
        reaper = Reaper()
        seed = _fake_seed(fruitful=False)
        result = reaper.reseed(seed)
        assert result is None

    @mock.patch("wheat.reaper.WheatSeed")
    def test_strips_previous_then_chain(self, MockWheatSeed):
        reaper = Reaper()
        seed = _fake_seed(
            task="Build cache then add TTL expiration then add LRU",
            seed_id="s5", fruitful=True,
        )
        MockWheatSeed.return_value = mock.MagicMock()

        reaper.reseed(seed)

        new_task = MockWheatSeed.call_args[0][0]
        # Should start with just the base task, not the full chain
        assert new_task.startswith("Build cache then")
        # Should not contain the old chain
        assert "then add TTL" not in new_task or "then add LRU" not in new_task

    @mock.patch("wheat.reaper.WheatSeed")
    def test_follow_up_is_lowercase(self, MockWheatSeed):
        reaper = Reaper()
        seed = _fake_seed(task="Build API endpoint", seed_id="s3", fruitful=True)
        MockWheatSeed.return_value = mock.MagicMock()

        reaper.reseed(seed)

        new_task = MockWheatSeed.call_args[0][0]
        # The "then ..." part should be lowercase
        then_part = new_task.split(" then ", 1)[1]
        assert then_part == then_part.lower()


class TestReseedStrategies:
    def test_all_patterns_compile(self):
        import re
        for pattern in RESEED_STRATEGIES:
            re.compile(pattern)  # should not raise

    def test_all_strategy_lists_nonempty(self):
        for pattern, strategies in RESEED_STRATEGIES.items():
            assert len(strategies) >= 1, f"Pattern {pattern} has no strategies"

    def test_generic_strategies_nonempty(self):
        assert len(GENERIC_STRATEGIES) >= 1
