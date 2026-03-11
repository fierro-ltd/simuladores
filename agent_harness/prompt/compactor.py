"""Compaction strategy: manages context window usage.

Primary: Anthropic compaction API (compact-2026-01-12 beta).
Fallback: Custom Session Bridge (Temporal child workflow).

Activates when working messages reach 80% of context window.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CompactionStrategy(StrEnum):
    ANTHROPIC_API = "anthropic_api"
    SESSION_BRIDGE = "session_bridge"


@dataclass
class CompactionConfig:
    """Configuration for context window compaction."""

    threshold: float = 0.8
    max_tokens: int = 128_000
    strategy: CompactionStrategy = CompactionStrategy.ANTHROPIC_API
    # Fields that should never be compacted (e.g., input_snapshot during QA)
    protected_fields: list[str] | None = None


def should_compact(
    current_tokens: int, max_tokens: int, threshold: float = 0.8
) -> bool:
    """Check if compaction should trigger based on token usage."""
    return current_tokens >= (max_tokens * threshold)
