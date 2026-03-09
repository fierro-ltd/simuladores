"""Tests for in-memory rate limiter."""

from __future__ import annotations

import time

import pytest

from agent_harness.gateway.rate_limiter import InMemoryRateLimiter, RateLimitResult


class TestRateLimitResult:
    """RateLimitResult dataclass tests."""

    def test_frozen(self):
        r = RateLimitResult(allowed=True, remaining=5)
        with pytest.raises(AttributeError):
            r.allowed = False  # type: ignore[misc]

    def test_defaults(self):
        r = RateLimitResult(allowed=True, remaining=3)
        assert r.retry_after == 0.0


class TestInMemoryRateLimiter:
    """InMemoryRateLimiter tests."""

    def test_disabled_when_max_zero(self):
        rl = InMemoryRateLimiter(max_requests=0)
        assert rl.enabled is False
        result = rl.check("caller")
        assert result.allowed is True

    def test_basic_allow(self):
        rl = InMemoryRateLimiter(max_requests=3, window_seconds=60)
        r1 = rl.check("c1")
        assert r1.allowed is True
        assert r1.remaining == 2

    def test_basic_block(self):
        rl = InMemoryRateLimiter(max_requests=2, window_seconds=60)
        rl.check("c1")
        rl.check("c1")
        r3 = rl.check("c1")
        assert r3.allowed is False
        assert r3.remaining == 0
        assert r3.retry_after > 0

    def test_per_caller_isolation(self):
        rl = InMemoryRateLimiter(max_requests=1, window_seconds=60)
        assert rl.check("c1").allowed is True
        assert rl.check("c1").allowed is False
        # Different caller still allowed
        assert rl.check("c2").allowed is True

    def test_remaining_decreases(self):
        rl = InMemoryRateLimiter(max_requests=3, window_seconds=60)
        assert rl.check("c1").remaining == 2
        assert rl.check("c1").remaining == 1
        assert rl.check("c1").remaining == 0  # third uses the last slot
        assert rl.check("c1").allowed is False

    def test_window_reset(self):
        """After the window expires, requests are allowed again."""
        rl = InMemoryRateLimiter(max_requests=1, window_seconds=0.1)
        assert rl.check("c1").allowed is True
        assert rl.check("c1").allowed is False
        time.sleep(0.15)
        assert rl.check("c1").allowed is True

    def test_disabled_always_passes(self):
        rl = InMemoryRateLimiter(max_requests=0, window_seconds=1)
        for _ in range(100):
            assert rl.check("c1").allowed is True
