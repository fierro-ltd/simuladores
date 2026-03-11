"""Anthropic compaction API client wrapper.

Wraps the Anthropic API for message compaction, with field protection
and strategy selection. Calls the Anthropic messages API to produce
a compacted summary, then builds a reduced message list.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from agent_harness.prompt.compactor import (
    CompactionConfig,
    CompactionStrategy,
    should_compact,
)

logger = logging.getLogger(__name__)

COMPACTION_SYSTEM_PROMPT = (
    "You are a conversation compactor for an AI agent system. "
    "Summarize the conversation so far into a concise briefing. "
    "You MUST preserve the following verbatim:\n"
    "- All compliance verdicts and their reasoning\n"
    "- All citations and source references\n"
    "- All document facts and extracted data\n"
    "- All tool call results and their outputs\n"
    "- The full operativo plan (PLAN.md contents)\n"
    "Omit chitchat, redundant clarifications, and superseded drafts. "
    "Output a single assistant message with the compacted briefing."
)

_RECENT_MESSAGES_KEEP = 10


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

    async def compact(
        self,
        anthropic_client: Any,
        system_prompt: str,
        messages: list[dict[str, str]],
        operativo_id: str,
    ) -> CompactionResult:
        """Compact conversation messages via the Anthropic API.

        Calls anthropic_client.messages.create() with a compaction system
        prompt, then builds a reduced message list: summary + last N recent
        messages.

        Args:
            anthropic_client: AsyncAnthropicVertex instance.
            system_prompt: The agent's system prompt.
            messages: Full conversation message list.
            operativo_id: Current operativo ID for logging.

        Returns:
            CompactionResult with compacted messages and token counts.
        """
        request = self.build_request(system_prompt, messages)
        tokens_before = sum(
            len(m.get("content", "")) for m in messages
        )

        compaction_prompt = (
            f"{COMPACTION_SYSTEM_PROMPT}\n\n"
            f"Operativo: {operativo_id}\n"
            f"Original system prompt:\n{system_prompt}"
        )

        response = await anthropic_client.messages.create(
            model=request.model,
            max_tokens=4096,
            system=compaction_prompt,
            messages=messages,
        )

        # Extract summary text from the API response.
        summary_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                summary_text += block.text

        summary_message = {"role": "assistant", "content": summary_text}

        # Keep last N recent messages to preserve immediate context.
        recent = messages[-_RECENT_MESSAGES_KEEP:] if len(messages) > _RECENT_MESSAGES_KEEP else list(messages)
        compacted = [summary_message] + recent

        tokens_after = sum(len(m.get("content", "")) for m in compacted)

        logger.info(
            "Compaction complete for operativo %s: %d -> %d chars",
            operativo_id,
            tokens_before,
            tokens_after,
        )

        return CompactionResult(
            compacted_messages=compacted,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            strategy_used=CompactionStrategy.ANTHROPIC_API,
            protected_fields_preserved=len(request.protected_content),
        )
