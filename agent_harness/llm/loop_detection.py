"""Loop detection: tracks per-resource tool call repetition to prevent doom loops."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ResourceEditTracker:
    """Tracks how many times each resource/operation is invoked in a session.

    Injects 'reconsider approach' guidance after threshold is exceeded.
    """

    threshold: int = 5
    _counts: dict[str, int] = field(default_factory=dict)

    def record(self, tool_name: str, args: dict) -> str | None:
        """Record a tool call. Returns guidance string if threshold exceeded, None otherwise."""
        resource = self._extract_resource(tool_name, args)
        if not resource:
            return None
        self._counts[resource] = self._counts.get(resource, 0) + 1
        if self._counts[resource] >= self.threshold:
            return (
                f"[HARNESS] You have called {tool_name} on '{resource}' "
                f"{self._counts[resource]} times. "
                f"Consider stepping back and reconsidering your approach entirely."
            )
        return None

    def _extract_resource(self, tool_name: str, args: dict) -> str | None:
        """Extract the resource identifier from a tool call."""
        # For execute_api, the resource is the operation name
        if tool_name == "execute_api":
            return args.get("operation", "")
        # For other tools, use tool_name as the resource
        return tool_name

    @property
    def counts(self) -> dict[str, int]:
        """Return current counts (read-only copy)."""
        return dict(self._counts)

    def reset(self) -> None:
        """Reset all counters."""
        self._counts.clear()
