"""Tests for InMemoryGraphStore."""

import uuid

import pytest

from agent_harness.memory.embeddings import FakeEmbeddingClient
from agent_harness.memory.graph import (
    MemoryEdge,
    MemoryType,
    RelationType,
)
from agent_harness.memory.graph_store import InMemoryGraphStore


class TestGraphStoreCRUD:
    @pytest.fixture
    def store(self):
        return InMemoryGraphStore(embedder=FakeEmbeddingClient(dimensions=8))

    @pytest.mark.asyncio
    async def test_store_returns_uuid(self, store):
        node_id = await store.store(
            domain="dce",
            content="Toys require ASTM F963 testing.",
            memory_type=MemoryType.FACT,
        )
        assert isinstance(node_id, uuid.UUID)

    @pytest.mark.asyncio
    async def test_get_returns_stored_node(self, store):
        node_id = await store.store(
            domain="dce",
            content="Age grading mandatory for toys.",
            memory_type=MemoryType.FACT,
            importance=0.8,
            source="op-1",
            metadata={"standard": "ASTM"},
        )
        node = await store.get(node_id)
        assert node is not None
        assert node.content == "Age grading mandatory for toys."
        assert node.memory_type == MemoryType.FACT
        assert node.importance == 0.8
        assert node.source == "op-1"
        assert node.metadata == {"standard": "ASTM"}

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self, store):
        assert await store.get(uuid.uuid4()) is None

    @pytest.mark.asyncio
    async def test_forget_soft_deletes(self, store):
        node_id = await store.store(
            domain="dce",
            content="Obsolete pattern.",
            memory_type=MemoryType.PATTERN,
        )
        assert await store.forget(node_id) is True
        assert await store.get(node_id) is None

    @pytest.mark.asyncio
    async def test_forget_nonexistent_returns_false(self, store):
        assert await store.forget(uuid.uuid4()) is False

    @pytest.mark.asyncio
    async def test_store_auto_embeds(self, store):
        node_id = await store.store(
            domain="dce",
            content="Some text to embed.",
            memory_type=MemoryType.FACT,
        )
        node = await store.get(node_id)
        assert node is not None
        assert len(node.embedding) == 8

    @pytest.mark.asyncio
    async def test_list_by_domain(self, store):
        await store.store(domain="dce", content="DCE fact.", memory_type=MemoryType.FACT)
        await store.store(domain="has", content="HAS fact.", memory_type=MemoryType.FACT)
        nodes = await store.list_by_domain("dce")
        assert len(nodes) == 1
        assert nodes[0].domain == "dce"

    @pytest.mark.asyncio
    async def test_list_by_domain_empty(self, store):
        nodes = await store.list_by_domain("dce")
        assert nodes == []


class TestGraphStoreEdges:
    @pytest.fixture
    def store(self):
        return InMemoryGraphStore(embedder=FakeEmbeddingClient(dimensions=8))

    @pytest.mark.asyncio
    async def test_add_and_get_edge(self, store):
        id1 = await store.store(domain="dce", content="Old fact.", memory_type=MemoryType.FACT)
        id2 = await store.store(domain="dce", content="New fact.", memory_type=MemoryType.FACT)
        edge = MemoryEdge(source_id=id2, target_id=id1, relation=RelationType.UPDATES)
        await store.add_edge(edge)
        neighbors = await store.get_neighbors(id2)
        assert len(neighbors) == 1
        node, e = neighbors[0]
        assert node.content == "Old fact."
        assert e.relation == RelationType.UPDATES

    @pytest.mark.asyncio
    async def test_bidirectional_lookup(self, store):
        id1 = await store.store(domain="dce", content="Cause.", memory_type=MemoryType.FACT)
        id2 = await store.store(domain="dce", content="Effect.", memory_type=MemoryType.FACT)
        await store.add_edge(MemoryEdge(source_id=id1, target_id=id2, relation=RelationType.CAUSED_BY))
        neighbors = await store.get_neighbors(id2)
        assert len(neighbors) == 1
        assert neighbors[0][0].content == "Cause."

    @pytest.mark.asyncio
    async def test_filter_by_relation(self, store):
        id1 = await store.store(domain="dce", content="Node A.", memory_type=MemoryType.FACT)
        id2 = await store.store(domain="dce", content="Node B.", memory_type=MemoryType.FACT)
        id3 = await store.store(domain="dce", content="Node C.", memory_type=MemoryType.FACT)
        await store.add_edge(MemoryEdge(source_id=id1, target_id=id2, relation=RelationType.UPDATES))
        await store.add_edge(MemoryEdge(source_id=id1, target_id=id3, relation=RelationType.RELATED_TO))
        updates = await store.get_neighbors(id1, relation=RelationType.UPDATES)
        assert len(updates) == 1
        assert updates[0][0].content == "Node B."

    @pytest.mark.asyncio
    async def test_no_neighbors(self, store):
        nid = await store.store(domain="dce", content="Alone.", memory_type=MemoryType.FACT)
        assert await store.get_neighbors(nid) == []

    @pytest.mark.asyncio
    async def test_edges_with_store_method(self, store):
        id1 = await store.store(domain="dce", content="First.", memory_type=MemoryType.FACT)
        id2 = await store.store(
            domain="dce",
            content="Second.",
            memory_type=MemoryType.FACT,
            edges=[MemoryEdge(source_id=uuid.UUID(int=0), target_id=id1, relation=RelationType.UPDATES)],
        )
        neighbors = await store.get_neighbors(id2)
        assert len(neighbors) == 1


class TestGraphStoreSearch:
    @pytest.fixture
    def store(self):
        return InMemoryGraphStore(embedder=FakeEmbeddingClient(dimensions=8))

    @pytest.mark.asyncio
    async def test_search_returns_results(self, store):
        await store.store(domain="dce", content="ASTM F963 safety.", memory_type=MemoryType.FACT)
        await store.store(domain="dce", content="EN 71 European.", memory_type=MemoryType.FACT)
        results = await store.search("dce", "toy safety standards")
        assert len(results) >= 1
        assert all(r.domain == "dce" for r in results)

    @pytest.mark.asyncio
    async def test_search_respects_domain(self, store):
        await store.store(domain="dce", content="DCE specific.", memory_type=MemoryType.FACT)
        await store.store(domain="has", content="HAS specific.", memory_type=MemoryType.FACT)
        results = await store.search("dce", "specific")
        assert len(results) == 1
        assert results[0].domain == "dce"

    @pytest.mark.asyncio
    async def test_search_respects_memory_types_filter(self, store):
        await store.store(domain="dce", content="A fact.", memory_type=MemoryType.FACT)
        await store.store(domain="dce", content="A decision.", memory_type=MemoryType.DECISION)
        results = await store.search("dce", "something", memory_types=[MemoryType.FACT])
        assert all(r.memory_type == MemoryType.FACT for r in results)

    @pytest.mark.asyncio
    async def test_search_excludes_forgotten(self, store):
        nid = await store.store(domain="dce", content="Forgotten.", memory_type=MemoryType.FACT)
        await store.forget(nid)
        results = await store.search("dce", "Forgotten")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_match_count_limit(self, store):
        for i in range(20):
            await store.store(domain="dce", content=f"Pattern number {i}.", memory_type=MemoryType.PATTERN)
        results = await store.search("dce", "pattern", match_count=5)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_search_empty_store(self, store):
        results = await store.search("dce", "anything")
        assert results == []
