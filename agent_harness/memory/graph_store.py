"""Memory graph store implementations.

InMemoryGraphStore: dict-backed store for tests (no DB required).
PostgresGraphStore: asyncpg+pgvector store for production (Task 5).
"""

from __future__ import annotations

import uuid
from typing import Any

from agent_harness.memory.embeddings import EmbeddingClient
from agent_harness.memory.graph import (
    MemoryEdge,
    MemoryNode,
    MemoryType,
    RelationType,
)

# Sentinel UUID used as placeholder in edges passed to store()
_PLACEHOLDER_UUID = uuid.UUID(int=0)


class InMemoryGraphStore:
    """In-memory graph store for testing. Same interface as PostgresGraphStore."""

    def __init__(self, embedder: EmbeddingClient) -> None:
        self._embedder = embedder
        self._nodes: dict[uuid.UUID, MemoryNode] = {}
        self._edges: list[MemoryEdge] = []
        self._forgotten: set[uuid.UUID] = set()

    async def store(
        self,
        domain: str,
        content: str,
        memory_type: MemoryType,
        importance: float = 0.5,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
        edges: list[MemoryEdge] | None = None,
    ) -> uuid.UUID:
        """Store a memory node, auto-generating embedding."""
        embedding = await self._embedder.embed_document(content)
        node_id = uuid.uuid4()
        node = MemoryNode(
            id=node_id,
            domain=domain,
            content=content,
            memory_type=memory_type,
            importance=importance,
            embedding=embedding,
            source=source,
            metadata=metadata or {},
        )
        self._nodes[node_id] = node
        if edges:
            for e in edges:
                # Replace placeholder source_id with actual new node id
                actual_source = node_id if e.source_id == _PLACEHOLDER_UUID else e.source_id
                actual_target = node_id if e.target_id == _PLACEHOLDER_UUID else e.target_id
                self._edges.append(MemoryEdge(
                    source_id=actual_source,
                    target_id=actual_target,
                    relation=e.relation,
                    weight=e.weight,
                ))
        return node_id

    async def get(self, node_id: uuid.UUID) -> MemoryNode | None:
        """Get a node by ID. Returns None if missing or forgotten."""
        if node_id in self._forgotten:
            return None
        return self._nodes.get(node_id)

    async def forget(self, node_id: uuid.UUID) -> bool:
        """Soft-delete a node. Returns True if it existed and wasn't already forgotten."""
        if node_id in self._nodes and node_id not in self._forgotten:
            self._forgotten.add(node_id)
            return True
        return False

    async def list_by_domain(self, domain: str) -> list[MemoryNode]:
        """List all non-forgotten nodes for a domain."""
        return [
            n for n in self._nodes.values()
            if n.domain == domain and n.id not in self._forgotten
        ]

    async def add_edge(self, edge: MemoryEdge) -> None:
        """Add a directed edge between two nodes."""
        self._edges.append(edge)

    async def get_neighbors(
        self, node_id: uuid.UUID, relation: RelationType | None = None,
    ) -> list[tuple[MemoryNode, MemoryEdge]]:
        """Get all connected nodes (bidirectional), optionally filtered by relation."""
        results: list[tuple[MemoryNode, MemoryEdge]] = []
        for e in self._edges:
            if relation and e.relation != relation:
                continue
            other_id: uuid.UUID | None = None
            if e.source_id == node_id:
                other_id = e.target_id
            elif e.target_id == node_id:
                other_id = e.source_id
            if other_id and other_id not in self._forgotten:
                other = self._nodes.get(other_id)
                if other:
                    results.append((other, e))
        return results

    async def search(
        self,
        domain: str,
        query: str,
        *,
        match_count: int = 10,
        memory_types: list[MemoryType] | None = None,
    ) -> list[MemoryNode]:
        """Search by cosine similarity (in-memory approximation of hybrid search)."""
        import math

        query_emb = await self._embedder.embed_query(query)
        candidates = [
            n for n in self._nodes.values()
            if n.domain == domain
            and n.id not in self._forgotten
            and (memory_types is None or n.memory_type in memory_types)
        ]

        def cosine(a: list[float], b: list[float]) -> float:
            if len(a) != len(b) or not a:
                return 0.0
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(x * x for x in b))
            if na == 0 or nb == 0:
                return 0.0
            return dot / (na * nb)

        scored = [(n, cosine(query_emb, n.embedding)) for n in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [n for n, _ in scored[:match_count]]
