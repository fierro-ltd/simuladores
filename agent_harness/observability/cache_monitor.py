"""Cache hit rate monitoring per domain/agent pair.

Tracks Anthropic prompt cache utilization across all LLM calls,
enabling visibility into cache efficiency by domain and agent.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from agent_harness.llm.client import TokenUsage


@dataclass(frozen=True)
class CacheStats:
    """Aggregated cache statistics for a (domain, agent) pair."""

    domain: str
    agent: str
    total_calls: int = 0
    total_input_tokens: int = 0
    total_cache_creation: int = 0
    total_cache_read: int = 0

    @property
    def cache_hit_rate(self) -> float:
        """Fraction of cacheable tokens served from cache (0.0-1.0)."""
        total = self.total_cache_creation + self.total_cache_read
        if total == 0:
            return 0.0
        return self.total_cache_read / total


class CacheMonitor:
    """Accumulates cache statistics per (domain, agent) key.

    Thread-safe: uses a lock for concurrent recording from
    multiple Temporal activity threads.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[tuple[str, str], dict[str, int]] = {}

    def record(self, domain: str, agent: str, usage: TokenUsage) -> None:
        """Record token usage from a single LLM call."""
        key = (domain, agent)
        with self._lock:
            if key not in self._data:
                self._data[key] = {
                    "total_calls": 0,
                    "total_input_tokens": 0,
                    "total_cache_creation": 0,
                    "total_cache_read": 0,
                }
            bucket = self._data[key]
            bucket["total_calls"] += 1
            bucket["total_input_tokens"] += usage.input_tokens
            bucket["total_cache_creation"] += usage.cache_creation_tokens
            bucket["total_cache_read"] += usage.cache_read_tokens

    def get_stats(self, domain: str, agent: str) -> CacheStats:
        """Return stats for a specific (domain, agent) pair.

        Returns a zeroed CacheStats if the pair has not been recorded.
        """
        key = (domain, agent)
        with self._lock:
            bucket = self._data.get(key)
        if bucket is None:
            return CacheStats(domain=domain, agent=agent)
        return CacheStats(
            domain=domain,
            agent=agent,
            total_calls=bucket["total_calls"],
            total_input_tokens=bucket["total_input_tokens"],
            total_cache_creation=bucket["total_cache_creation"],
            total_cache_read=bucket["total_cache_read"],
        )

    def all_stats(self) -> list[CacheStats]:
        """Return stats for all tracked (domain, agent) pairs."""
        with self._lock:
            keys = list(self._data.keys())
        return [self.get_stats(domain, agent) for domain, agent in keys]

    def summary(self) -> dict:
        """Return a summary dict suitable for JSON serialization.

        Returns:
            {"by_domain_agent": [...], "overall_hit_rate": float}
        """
        stats = self.all_stats()
        entries = []
        overall_creation = 0
        overall_read = 0
        for s in stats:
            entries.append({
                "domain": s.domain,
                "agent": s.agent,
                "total_calls": s.total_calls,
                "total_input_tokens": s.total_input_tokens,
                "total_cache_creation": s.total_cache_creation,
                "total_cache_read": s.total_cache_read,
                "cache_hit_rate": s.cache_hit_rate,
            })
            overall_creation += s.total_cache_creation
            overall_read += s.total_cache_read

        total = overall_creation + overall_read
        overall_rate = overall_read / total if total > 0 else 0.0

        return {
            "by_domain_agent": entries,
            "overall_hit_rate": overall_rate,
        }
