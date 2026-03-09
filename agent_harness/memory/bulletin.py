"""Cortex Bulletin: cross-session memory summaries.

Generates periodic LLM-summarised bulletins from the memory graph,
injected into PromptBuilder L3 as semantic patterns.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class BulletinConfig:
    """Configuration for bulletin generation."""

    interval_minutes: int = 60
    max_patterns: int = 20
    max_tokens: int = 500
    model: str = "claude-sonnet-4-6"
    domain: str = "dce"


@dataclass(frozen=True)
class Bulletin:
    """A cross-session memory summary for a domain."""

    domain: str
    summary: str
    pattern_count: int
    generated_at: str  # ISO 8601

    def as_pattern_string(self) -> str:
        """Format for PromptBuilder L3 injection."""
        if not self.summary:
            return ""
        return f"[bulletin] {self.summary}"

    def is_stale(self, now: datetime, max_age_minutes: int = 60) -> bool:
        """Check if the bulletin is older than max_age_minutes."""
        generated = datetime.fromisoformat(self.generated_at)
        # Ensure both are timezone-aware for comparison
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        age_seconds = (now - generated).total_seconds()
        return age_seconds > max_age_minutes * 60


async def generate_bulletin(
    client: object,
    recall: object,
    config: BulletinConfig,
) -> Bulletin:
    """Generate a bulletin by summarising recent memory patterns.

    Args:
        client: Any object with an async send_message method
            (e.g. AnthropicClient). Called as
            client.send_message(prompt=..., model=config.model).
        recall: MemoryRecall instance with retrieve_patterns().
        config: BulletinConfig controlling generation parameters.

    Returns:
        Bulletin with LLM-generated summary, or empty bulletin if no patterns.
    """
    from agent_harness.memory.recall import MemoryRecall

    assert isinstance(recall, MemoryRecall)

    patterns = await recall.retrieve_patterns(
        domain=config.domain,
        query="recent patterns and learnings",
        top_k=config.max_patterns,
    )

    now = datetime.now(timezone.utc).isoformat()

    if not patterns:
        return Bulletin(
            domain=config.domain,
            summary="",
            pattern_count=0,
            generated_at=now,
        )

    # Build a prompt dict matching PromptBuilder.build() output format
    prompt = {
        "system": (
            "You are a memory summariser for the agent harness. "
            "Summarise the following cross-session memory patterns into a concise "
            "bulletin (1-3 sentences) that captures the most important learnings. "
            "Be specific and actionable."
        ),
        "messages": [
            {
                "role": "user",
                "content": f"Summarise these {len(patterns)} patterns:\n\n"
                + "\n".join(f"- {p}" for p in patterns),
            }
        ],
        "cache_control": {},
    }

    result = await client.send_message(prompt=prompt, model=config.model)

    return Bulletin(
        domain=config.domain,
        summary=result.content,
        pattern_count=len(patterns),
        generated_at=now,
    )
