"""Tests for semantic store."""

from agent_harness.memory.semantic_store import Pattern, SemanticStore


class TestSemanticStore:
    def test_store_and_retrieve(self):
        store = SemanticStore.in_memory()
        p = Pattern(
            domain="dce",
            category="error",
            description="Missing age grading",
            embedding=[1.0, 0.0, 0.0],
        )
        store.store(p)
        results = store.retrieve("dce", query_embedding=[1.0, 0.0, 0.0])
        assert len(results) == 1
        assert results[0].description == "Missing age grading"

    def test_domain_isolation(self):
        store = SemanticStore.in_memory()
        store.store(Pattern(domain="dce", category="a", description="DCE pattern", embedding=[1.0, 0.0]))
        store.store(Pattern(domain="has", category="b", description="HAS pattern", embedding=[1.0, 0.0]))
        results = store.retrieve("dce", query_embedding=[1.0, 0.0])
        assert len(results) == 1
        assert results[0].domain == "dce"

    def test_top_k_limit(self):
        store = SemanticStore.in_memory()
        for i in range(10):
            store.store(Pattern(
                domain="dce",
                category="cat",
                description=f"pattern-{i}",
                embedding=[float(i), 1.0],
            ))
        results = store.retrieve("dce", query_embedding=[9.0, 1.0], top_k=3)
        assert len(results) == 3

    def test_empty_store(self):
        store = SemanticStore.in_memory()
        results = store.retrieve("dce", query_embedding=[1.0, 0.0])
        assert results == []

    def test_similarity_ordering(self):
        store = SemanticStore.in_memory()
        store.store(Pattern(domain="dce", category="a", description="close", embedding=[1.0, 0.0, 0.0]))
        store.store(Pattern(domain="dce", category="b", description="far", embedding=[0.0, 1.0, 0.0]))
        results = store.retrieve("dce", query_embedding=[1.0, 0.0, 0.0], top_k=2)
        assert results[0].description == "close"
        assert results[1].description == "far"
