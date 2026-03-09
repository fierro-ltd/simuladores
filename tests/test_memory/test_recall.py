"""Tests for the recall layer that bridges graph store to prompt builder."""

import pytest

from agent_harness.memory.embeddings import FakeEmbeddingClient
from agent_harness.memory.graph import MemoryType
from agent_harness.memory.graph_store import InMemoryGraphStore
from agent_harness.memory.recall import MemoryRecall


class TestMemoryRecall:
    @pytest.fixture
    def recall(self):
        store = InMemoryGraphStore(embedder=FakeEmbeddingClient(dimensions=8))
        return MemoryRecall(store=store)

    @pytest.mark.asyncio
    async def test_recall_returns_strings(self, recall):
        await recall.store.store(
            domain="dce",
            content="Toys for children under 3 require small parts testing.",
            memory_type=MemoryType.FACT,
        )
        patterns = await recall.retrieve_patterns("dce", "small parts testing")
        assert isinstance(patterns, list)
        assert all(isinstance(p, str) for p in patterns)
        assert len(patterns) == 1

    @pytest.mark.asyncio
    async def test_recall_format_includes_type(self, recall):
        await recall.store.store(
            domain="dce",
            content="Always verify manufacturer name.",
            memory_type=MemoryType.PATTERN,
        )
        patterns = await recall.retrieve_patterns("dce", "manufacturer")
        assert len(patterns) == 1
        assert "[pattern]" in patterns[0]
        assert "Always verify manufacturer name." in patterns[0]

    @pytest.mark.asyncio
    async def test_recall_empty_returns_empty(self, recall):
        patterns = await recall.retrieve_patterns("dce", "anything")
        assert patterns == []

    @pytest.mark.asyncio
    async def test_recall_respects_top_k(self, recall):
        for i in range(10):
            await recall.store.store(
                domain="dce",
                content=f"Pattern {i}.",
                memory_type=MemoryType.PATTERN,
            )
        patterns = await recall.retrieve_patterns("dce", "pattern", top_k=3)
        assert len(patterns) == 3

    @pytest.mark.asyncio
    async def test_recall_domain_isolation(self, recall):
        await recall.store.store(domain="dce", content="DCE.", memory_type=MemoryType.FACT)
        await recall.store.store(domain="has", content="HAS.", memory_type=MemoryType.FACT)
        patterns = await recall.retrieve_patterns("has", "something")
        assert len(patterns) == 1
        assert "HAS." in patterns[0]

    @pytest.mark.asyncio
    async def test_compatible_with_prompt_builder(self, recall):
        """Verify output is list[str] compatible with PromptBuilder.set_semantic_patterns()."""
        await recall.store.store(
            domain="dce",
            content="Test pattern.",
            memory_type=MemoryType.PATTERN,
        )
        results = await recall.retrieve_patterns("dce", "test")
        assert isinstance(results, list)
        assert all(isinstance(s, str) for s in results)
