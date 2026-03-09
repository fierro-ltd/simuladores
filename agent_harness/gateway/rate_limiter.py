"""In-memory sliding-window rate limiter.

Per-caller request counting with configurable window and max requests.
When disabled (max_requests=0), all requests pass unconditionally.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitResult:
    """Result of a rate-limit check."""

    allowed: bool
    remaining: int
    retry_after: float = 0.0


class InMemoryRateLimiter:
    """Sliding-window per-caller rate limiter.

    Parameters
    ----------
    max_requests:
        Maximum requests per caller per window.  ``0`` disables limiting.
    window_seconds:
        Length of the sliding window in seconds.
    """

    def __init__(self, max_requests: int = 0, window_seconds: float = 60.0) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._enabled = max_requests > 0
        self._requests: dict[str, list[float]] = defaultdict(list)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def check(self, caller_id: str) -> RateLimitResult:
        """Check whether *caller_id* is within the rate limit.

        Returns a ``RateLimitResult`` indicating whether the request
        is allowed, how many requests remain in the window, and (if
        blocked) how many seconds until the caller can retry.
        """
        if not self._enabled:
            return RateLimitResult(allowed=True, remaining=0)

        now = time.monotonic()
        cutoff = now - self._window

        # Prune expired timestamps
        timestamps = self._requests[caller_id]
        self._requests[caller_id] = [ts for ts in timestamps if ts > cutoff]
        timestamps = self._requests[caller_id]

        if len(timestamps) >= self._max:
            oldest = timestamps[0]
            retry_after = oldest + self._window - now
            return RateLimitResult(
                allowed=False,
                remaining=0,
                retry_after=max(retry_after, 0.0),
            )

        timestamps.append(now)
        remaining = self._max - len(timestamps)
        return RateLimitResult(allowed=True, remaining=remaining)
