"""Typed memory graph: node and edge definitions.

Five memory types (Fact, Decision, Pattern, Preference, Error) with
four relationship types (Updates, Contradicts, CausedBy, RelatedTo).
Used by MemoryGraphStore (PostgreSQL+pgvector) for cross-job learning.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MemoryType(str, Enum):
    """Type of memory node. Controls default importance and decay."""

    FACT = "fact"
    DECISION = "decision"
    PATTERN = "pattern"
    PREFERENCE = "preference"
    ERROR = "error"


class RelationType(str, Enum):
    """Type of directed edge between memory nodes."""

    UPDATES = "updates"
    CONTRADICTS = "contradicts"
    CAUSED_BY = "caused_by"
    RELATED_TO = "related_to"


@dataclass
class MemoryNode:
    """A typed memory node with optional embedding for semantic search."""

    domain: str
    content: str
    memory_type: MemoryType
    importance: float = 0.5
    embedding: list[float] = field(default_factory=list)
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: uuid.UUID | None = None
    rrf_score: float | None = None


@dataclass
class MemoryEdge:
    """A directed edge between two memory nodes."""

    source_id: uuid.UUID
    target_id: uuid.UUID
    relation: RelationType
    weight: float = 1.0
