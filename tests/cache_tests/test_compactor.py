"""Tests for compaction strategy."""

from agent_harness.prompt.compactor import (
    CompactionConfig,
    CompactionStrategy,
    should_compact,
)


class TestShouldCompact:
    def test_below_threshold_no_compaction(self):
        assert not should_compact(
            current_tokens=50_000, max_tokens=128_000, threshold=0.8
        )

    def test_above_threshold_triggers_compaction(self):
        assert should_compact(
            current_tokens=110_000, max_tokens=128_000, threshold=0.8
        )

    def test_exactly_at_threshold(self):
        assert should_compact(
            current_tokens=102_400, max_tokens=128_000, threshold=0.8
        )


class TestCompactionConfig:
    def test_default_config(self):
        config = CompactionConfig()
        assert config.threshold == 0.8
        assert config.max_tokens == 128_000
        assert config.strategy == CompactionStrategy.ANTHROPIC_API

    def test_custom_config(self):
        config = CompactionConfig(
            threshold=0.7,
            max_tokens=1_000_000,
            strategy=CompactionStrategy.SESSION_BRIDGE,
        )
        assert config.max_tokens == 1_000_000
