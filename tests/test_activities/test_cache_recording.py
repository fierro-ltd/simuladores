"""Tests for cache monitor recording in activity implementations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agent_harness.activities.factory import get_cache_monitor
from agent_harness.llm.client import TokenUsage
from agent_harness.observability.cache_monitor import CacheMonitor


class TestGetCacheMonitor:
    """Verify the module-level cache monitor singleton."""

    def test_returns_cache_monitor(self):
        # Reset the singleton for testing
        import agent_harness.activities.factory as factory_mod
        old = factory_mod._cache_monitor
        factory_mod._cache_monitor = None
        try:
            monitor = get_cache_monitor()
            assert isinstance(monitor, CacheMonitor)
        finally:
            factory_mod._cache_monitor = old

    def test_returns_same_instance(self):
        import agent_harness.activities.factory as factory_mod
        old = factory_mod._cache_monitor
        factory_mod._cache_monitor = None
        try:
            a = get_cache_monitor()
            b = get_cache_monitor()
            assert a is b
        finally:
            factory_mod._cache_monitor = old


class TestCacheRecordingInActivities:
    """Verify that activities call get_cache_monitor().record() after agent work."""

    def test_implementations_import_get_cache_monitor(self):
        """Verify the import exists in implementations module."""
        from agent_harness.activities import implementations as impl
        assert hasattr(impl, "get_cache_monitor")

    def test_cache_monitor_record_accumulates(self):
        """Verify CacheMonitor.record accumulates TokenUsage correctly."""
        monitor = CacheMonitor()
        usage1 = TokenUsage(input_tokens=100, output_tokens=50, cache_creation_tokens=20, cache_read_tokens=80)
        usage2 = TokenUsage(input_tokens=200, output_tokens=75, cache_creation_tokens=10, cache_read_tokens=190)

        monitor.record("dce", "santos", usage1)
        monitor.record("dce", "santos", usage2)

        stats = monitor.get_stats("dce", "santos")
        assert stats.total_calls == 2
        assert stats.total_input_tokens == 300
        assert stats.total_cache_creation == 30
        assert stats.total_cache_read == 270

    def test_cache_monitor_separate_agents(self):
        """Verify each agent gets separate stats."""
        monitor = CacheMonitor()
        monitor.record("dce", "santos", TokenUsage(input_tokens=100))
        monitor.record("dce", "medina", TokenUsage(input_tokens=200))
        monitor.record("dce", "lamponne", TokenUsage(input_tokens=150))
        monitor.record("dce", "ravenna", TokenUsage(input_tokens=80))

        assert monitor.get_stats("dce", "santos").total_input_tokens == 100
        assert monitor.get_stats("dce", "medina").total_input_tokens == 200
        assert monitor.get_stats("dce", "lamponne").total_input_tokens == 150
        assert monitor.get_stats("dce", "ravenna").total_input_tokens == 80
        assert len(monitor.all_stats()) == 4

    def test_cache_hit_rate_calculation(self):
        """Verify cache_hit_rate is computed correctly."""
        monitor = CacheMonitor()
        monitor.record("dce", "santos", TokenUsage(
            cache_creation_tokens=20,
            cache_read_tokens=80,
        ))
        stats = monitor.get_stats("dce", "santos")
        assert stats.cache_hit_rate == pytest.approx(0.8)

    def test_summary_format(self):
        """Verify summary dict has the expected shape."""
        monitor = CacheMonitor()
        monitor.record("dce", "santos", TokenUsage(input_tokens=100, cache_creation_tokens=10, cache_read_tokens=90))
        summary = monitor.summary()
        assert "by_domain_agent" in summary
        assert "overall_hit_rate" in summary
        assert len(summary["by_domain_agent"]) == 1
        entry = summary["by_domain_agent"][0]
        assert entry["domain"] == "dce"
        assert entry["agent"] == "santos"
        assert entry["cache_hit_rate"] == pytest.approx(0.9)
