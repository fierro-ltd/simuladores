"""Prompt builder enforcing strict layer ordering (Thariq's Law).

Layer order IS the architecture. Static content first, dynamic last.
This maximizes Anthropic API cache hits across sessions.

Order: L0 (system) → L1 (domain) → L3 (semantic) → L2 (session) → L4 (working)

PromptOrderViolation on any breach. CI must fail on cache-breaking changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class PromptOrderViolation(Exception):
    """Raised when prompt layers are assembled out of order.

    This is a CI-critical error. Cache-breaking changes must not ship.
    """


# Layer indices define the strict ordering.
_LAYER_NAMES = {
    0: "System Identity",
    1: "Domain Memory",
    2: "Session State",
    3: "Semantic Patterns",
    4: "Working Messages",
}

# Required ordering: L0 → L1 → L3 → L2 → L4
# (L3 before L2 because semantic patterns are more stable than session state)
_LAYER_ORDER = [0, 1, 3, 2, 4]


@dataclass
class PromptBuilder:
    """Assembles prompt messages in strict cache-optimised order.

    Usage:
        builder = PromptBuilder()
        builder.set_system_identity("You are Santos.")
        builder.set_domain_memory("# DCE Domain")
        builder.set_semantic_patterns(["pattern 1", "pattern 2"])
        builder.set_session_state("## Progress report")
        builder.add_working_message(role="user", content="Process this.")
        result = builder.build()
    """

    _system_identity: str | None = field(default=None, init=False)
    _domain_memory: str | None = field(default=None, init=False)
    _semantic_patterns: list[str] | None = field(default=None, init=False)
    _session_state: str | None = field(default=None, init=False)
    _working_messages: list[dict[str, str]] = field(default_factory=list, init=False)
    _last_layer: int = field(default=-1, init=False)

    def _check_order(self, layer: int) -> None:
        """Verify this layer comes after the previous one in _LAYER_ORDER."""
        if layer == self._last_layer:
            raise PromptOrderViolation(
                f"Layer {layer} ({_LAYER_NAMES[layer]}) already set"
            )
        expected_pos = _LAYER_ORDER.index(layer)
        current_pos = _LAYER_ORDER.index(self._last_layer) if self._last_layer >= 0 else -1
        if expected_pos <= current_pos:
            raise PromptOrderViolation(
                f"Layer {layer} ({_LAYER_NAMES[layer]}) set before "
                f"Layer {self._last_layer} ({_LAYER_NAMES[self._last_layer]})"
            )
        # Check that all preceding layers have been set
        for i in range(expected_pos):
            preceding = _LAYER_ORDER[i]
            if not self._is_layer_set(preceding):
                raise PromptOrderViolation(
                    f"Layer {layer} ({_LAYER_NAMES[layer]}) set before "
                    f"Layer {preceding} ({_LAYER_NAMES[preceding]})"
                )

    def _is_layer_set(self, layer: int) -> bool:
        return {
            0: self._system_identity is not None,
            1: self._domain_memory is not None,
            2: self._session_state is not None,
            3: self._semantic_patterns is not None,
            4: len(self._working_messages) > 0,
        }[layer]

    def set_system_identity(self, content: str) -> None:
        """Layer 0: Global system identity. Cached across ALL sessions."""
        self._check_order(0)
        self._system_identity = content
        self._last_layer = 0

    def set_domain_memory(self, content: str) -> None:
        """Layer 1: Domain memory (DCE.md, etc.). Cached across domain sessions."""
        self._check_order(1)
        self._domain_memory = content
        self._last_layer = 1

    def set_semantic_patterns(self, patterns: list[str]) -> None:
        """Layer 3: Cross-job semantic patterns. Injected as user message."""
        self._check_order(3)
        self._semantic_patterns = patterns
        self._last_layer = 3

    def set_session_state(self, content: str) -> None:
        """Layer 2: Session state (PROGRESS.md). Per-operativo."""
        self._check_order(2)
        self._session_state = content
        self._last_layer = 2

    def add_working_message(self, role: str, content: str) -> None:
        """Layer 4: Working messages. Current conversation only."""
        if not self._is_layer_set(2):
            self._check_order(4)
        self._working_messages.append({"role": role, "content": content})
        self._last_layer = 4

    def build(self) -> dict[str, Any]:
        """Assemble the final prompt structure for the Anthropic API.

        Returns dict with 'system', 'messages', and 'cache_control' keys.
        """
        if self._system_identity is None:
            raise PromptOrderViolation("System identity (Layer 0) is required but not set")

        # System prompt: L0 + L1 combined (both cached)
        system_parts = [self._system_identity]
        if self._domain_memory:
            system_parts.append(self._domain_memory)
        system_prompt = "\n\n".join(system_parts)

        # Messages: L3 (semantic) → L2 (session) → L4 (working)
        messages: list[dict[str, str]] = []

        # Semantic patterns as user message (never system prompt)
        if self._semantic_patterns:
            patterns_text = (
                "<semantic_patterns>\n"
                + "\n".join(f"- {p}" for p in self._semantic_patterns)
                + "\n</semantic_patterns>"
            )
            messages.append({"role": "user", "content": patterns_text})
            messages.append({
                "role": "assistant",
                "content": "Understood. I'll apply these learned patterns.",
            })

        # Session state as user message
        if self._session_state:
            messages.append({
                "role": "user",
                "content": f"<session_state>\n{self._session_state}\n</session_state>",
            })
            messages.append({
                "role": "assistant",
                "content": "Session state received. Continuing from last checkpoint.",
            })

        # Working messages last
        messages.extend(self._working_messages)

        # Cache control: mark system prompt for caching
        cache_control = {
            "system_cache": True,
            "system_token_estimate": len(system_prompt.split()) * 1.3,
        }

        return {
            "system": system_prompt,
            "messages": messages,
            "cache_control": cache_control,
        }
