"""Session Bridge — preserves critical fields during compaction.

Custom Temporal child workflow that routes to Anthropic API
for summarization while adding explicit "preserve" markers
for critical context that must survive compaction.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PreserveMarker:
    """Marks content that must survive compaction."""
    field_name: str
    content: str
    reason: str


@dataclass(frozen=True)
class SessionBridgeInput:
    """Input for the session bridge workflow."""
    operativo_id: str
    messages: list[dict[str, str]] = field(default_factory=list)
    preserve_markers: list[PreserveMarker] = field(default_factory=list)
    system_prompt: str = ""


@dataclass(frozen=True)
class SessionBridgeOutput:
    """Output from the session bridge workflow."""
    operativo_id: str
    compacted_messages: list[dict[str, str]] = field(default_factory=list)
    preserved_content: list[PreserveMarker] = field(default_factory=list)
    tokens_saved: int = 0


def build_preserve_markers(
    fields: dict[str, str], reason: str = "critical context"
) -> list[PreserveMarker]:
    """Build preserve markers for a dict of field_name -> content."""
    return [
        PreserveMarker(field_name=name, content=content, reason=reason)
        for name, content in fields.items()
    ]
