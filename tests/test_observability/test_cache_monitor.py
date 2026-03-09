"""Tests for cache hit rate monitor."""

import pytest

from agent_harness.llm.client import TokenUsage
from agent_harness.observability.cache_monitor import CacheMonitor, CacheStats


class TestCacheStats:
    def test_cache_hit_rate_zero_when_no_cache_tokens(self):
        stats = CacheStats(domain="dce", agent="santos")
        assert stats.cache_hit_rate == 0.0

    def test_cache_hit_rate_calculation(self):
        stats = CacheStats(
            domain="dce", agent="santos",
            total_cache_creation=200, total_cache_read=800,
        )
        assert stats.cache_hit_rate == pytest.approx(0.8)

    def test_frozen(self):
        stats = CacheStats(domain="dce", agent="santos")
        with pytest.raises(AttributeError):
            stats.total_calls = 5  # type: ignore[misc]


class TestCacheMonitor:
    def test_record_single_call(self):
        monitor = CacheMonitor()
        usage = TokenUsage(input_tokens=100, output_tokens=50,
                           cache_creation_tokens=30, cache_read_tokens=70)
        monitor.record("dce", "santos", usage)
        stats = monitor.get_stats("dce", "santos")
        assert stats.total_calls == 1
        assert stats.total_input_tokens == 100
        assert stats.total_cache_creation == 30
        assert stats.total_cache_read == 70

    def test_record_multiple_calls_accumulates(self):
        monitor = CacheMonitor()
        u1 = TokenUsage(input_tokens=100, output_tokens=50,
                        cache_creation_tokens=80, cache_read_tokens=20)
        u2 = TokenUsage(input_tokens=200, output_tokens=100,
                        cache_creation_tokens=20, cache_read_tokens=180)
        monitor.record("dce", "santos", u1)
        monitor.record("dce", "santos", u2)
        stats = monitor.get_stats("dce", "santos")
        assert stats.total_calls == 2
        assert stats.total_input_tokens == 300
        assert stats.total_cache_creation == 100
        assert stats.total_cache_read == 200

    def test_cache_hit_rate_calculation(self):
        monitor = CacheMonitor()
        # 200 creation + 800 read = 80% hit rate
        u1 = TokenUsage(input_tokens=500, output_tokens=100,
                        cache_creation_tokens=200, cache_read_tokens=300)
        u2 = TokenUsage(input_tokens=500, output_tokens=100,
                        cache_creation_tokens=0, cache_read_tokens=500)
        monitor.record("dce", "medina", u1)
        monitor.record("dce", "medina", u2)
        stats = monitor.get_stats("dce", "medina")
        assert stats.cache_hit_rate == pytest.approx(0.8)

    def test_different_domain_agent_pairs(self):
        monitor = CacheMonitor()
        u1 = TokenUsage(input_tokens=100, output_tokens=50)
        u2 = TokenUsage(input_tokens=200, output_tokens=100)
        monitor.record("dce", "santos", u1)
        monitor.record("has", "medina", u2)
        s1 = monitor.get_stats("dce", "santos")
        s2 = monitor.get_stats("has", "medina")
        assert s1.total_calls == 1
        assert s1.total_input_tokens == 100
        assert s2.total_calls == 1
        assert s2.total_input_tokens == 200

    def test_all_stats_returns_all(self):
        monitor = CacheMonitor()
        u = TokenUsage(input_tokens=100, output_tokens=50)
        monitor.record("dce", "santos", u)
        monitor.record("dce", "medina", u)
        monitor.record("has", "santos", u)
        stats = monitor.all_stats()
        assert len(stats) == 3
        pairs = {(s.domain, s.agent) for s in stats}
        assert pairs == {("dce", "santos"), ("dce", "medina"), ("has", "santos")}

    def test_summary_overall_rate(self):
        monitor = CacheMonitor()
        # Total: 100 creation + 300 read = 75% overall
        monitor.record("dce", "santos", TokenUsage(
            input_tokens=200, output_tokens=50,
            cache_creation_tokens=100, cache_read_tokens=100,
        ))
        monitor.record("dce", "medina", TokenUsage(
            input_tokens=200, output_tokens=50,
            cache_creation_tokens=0, cache_read_tokens=200,
        ))
        summary = monitor.summary()
        assert len(summary["by_domain_agent"]) == 2
        assert summary["overall_hit_rate"] == pytest.approx(0.75)

    def test_get_stats_missing_returns_zeros(self):
        monitor = CacheMonitor()
        stats = monitor.get_stats("nonexistent", "agent")
        assert stats.domain == "nonexistent"
        assert stats.agent == "agent"
        assert stats.total_calls == 0
        assert stats.total_input_tokens == 0
        assert stats.total_cache_creation == 0
        assert stats.total_cache_read == 0
        assert stats.cache_hit_rate == 0.0

    def test_summary_empty(self):
        monitor = CacheMonitor()
        summary = monitor.summary()
        assert summary["by_domain_agent"] == []
        assert summary["overall_hit_rate"] == 0.0
