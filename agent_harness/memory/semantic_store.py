"""Semantic memory store: in-memory stub for pattern storage and retrieval."""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Pattern:
    """A domain pattern with embedding for semantic retrieval."""

    domain: str
    category: str
    description: str
    embedding: list[float] = field(default_factory=list)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or len(a) == 0:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticStore:
    """In-memory semantic pattern store.

    This is a stub implementation. Production will use PostgreSQL + pgvector.
    """

    def __init__(self) -> None:
        self._patterns: list[Pattern] = []

    @classmethod
    def in_memory(cls) -> SemanticStore:
        """Create an in-memory semantic store."""
        return cls()

    def store(self, pattern: Pattern) -> None:
        """Store a pattern."""
        self._patterns.append(pattern)

    def retrieve(
        self, domain: str, query_embedding: list[float], top_k: int = 5
    ) -> list[Pattern]:
        """Retrieve top-k patterns by cosine similarity, filtered by domain."""
        domain_patterns = [p for p in self._patterns if p.domain == domain]
        scored = [
            (p, _cosine_similarity(query_embedding, p.embedding))
            for p in domain_patterns
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [p for p, _ in scored[:top_k]]
