"""In-memory bulletin store for Cortex Bulletin cross-session memory.

Stores the latest bulletin per domain, providing formatted pattern strings
for PromptBuilder L3 injection.
"""

from __future__ import annotations

from agent_harness.memory.bulletin import Bulletin


class InMemoryBulletinStore:
    """In-memory store for bulletins. Keeps latest per domain."""

    def __init__(self) -> None:
        self._bulletins: dict[str, Bulletin] = {}

    def save(self, bulletin: Bulletin) -> None:
        """Store a bulletin, replacing the existing one if newer."""
        existing = self._bulletins.get(bulletin.domain)
        if existing is None or bulletin.generated_at >= existing.generated_at:
            self._bulletins[bulletin.domain] = bulletin

    def get_latest(self, domain: str) -> Bulletin | None:
        """Get the latest bulletin for a domain, or None."""
        return self._bulletins.get(domain)

    def get_pattern_strings(self, domain: str) -> list[str]:
        """Get formatted pattern strings for PromptBuilder L3.

        Returns a list with one element (the formatted bulletin) or
        an empty list if no bulletin exists or the summary is empty.
        """
        bulletin = self._bulletins.get(domain)
        if bulletin is None:
            return []
        pattern = bulletin.as_pattern_string()
        if not pattern:
            return []
        return [pattern]
