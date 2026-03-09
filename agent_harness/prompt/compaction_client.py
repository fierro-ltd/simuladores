"""Anthropic compaction API client wrapper.

Wraps the Anthropic API for message compaction, with field protection
and strategy selection. Does NOT make actual API calls — provides the
type-safe interface and request/response models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_harness.prompt.compactor import (
    CompactionConfig,
    CompactionStrategy,
    should_compact,
)


@dataclass(frozen=True)
class CompactionRequest:
    """Request to compact conversation messages."""
    model: str = "compact-2026-01-12"
    system_prompt: str = ""
    messages: list[dict[str, str]] = field(default_factory=list)
    protected_content: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CompactionResult:
    """Result from a compaction operation."""
    compacted_messages: list[dict[str, str]] = field(default_factory=list)
    tokens_before: int = 0
    tokens_after: int = 0
    strategy_used: CompactionStrategy = CompactionStrategy.ANTHROPIC_API
    protected_fields_preserved: int = 0


class CompactionClient:
    """Client for managing context window compaction.

    Builds compaction requests with field protection,
    delegates to Anthropic API or Session Bridge strategy.
    """

    def __init__(self, config: CompactionConfig | None = None) -> None:
        self.config = config or CompactionConfig()

    def needs_compaction(self, current_tokens: int) -> bool:
        """Check if compaction should trigger."""
        return should_compact(
            current_tokens, self.config.max_tokens, self.config.threshold
        )

    def build_request(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        protected_content: list[str] | None = None,
    ) -> CompactionRequest:
        """Build a compaction request with field protection."""
        protected = list(protected_content or [])
        if self.config.protected_fields:
            protected.extend(self.config.protected_fields)
        return CompactionRequest(
            model="compact-2026-01-12",
            system_prompt=system_prompt,
            messages=list(messages),
            protected_content=protected,
        )

    def estimate_savings(self, tokens_before: int) -> int:
        """Estimate token savings from compaction (conservative 40% reduction)."""
        return int(tokens_before * 0.4)
