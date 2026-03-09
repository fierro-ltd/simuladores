"""Tests for memory graph type definitions."""

import uuid

from agent_harness.memory.graph import (
    MemoryEdge,
    MemoryNode,
    MemoryType,
    RelationType,
)


class TestMemoryType:
    def test_all_types_exist(self):
        assert MemoryType.FACT.value == "fact"
        assert MemoryType.DECISION.value == "decision"
        assert MemoryType.PATTERN.value == "pattern"
        assert MemoryType.PREFERENCE.value == "preference"
        assert MemoryType.ERROR.value == "error"

    def test_type_count(self):
        assert len(MemoryType) == 5

    def test_string_enum(self):
        assert isinstance(MemoryType.PATTERN, str)


class TestRelationType:
    def test_all_relations_exist(self):
        assert RelationType.UPDATES.value == "updates"
        assert RelationType.CONTRADICTS.value == "contradicts"
        assert RelationType.CAUSED_BY.value == "caused_by"
        assert RelationType.RELATED_TO.value == "related_to"

    def test_relation_count(self):
        assert len(RelationType) == 4


class TestMemoryNode:
    def test_create_minimal(self):
        node = MemoryNode(
            domain="dce",
            content="DCE documents require age grading for toys.",
            memory_type=MemoryType.FACT,
        )
        assert node.domain == "dce"
        assert node.importance == 0.5
        assert node.embedding == []
        assert node.source is None
        assert node.metadata == {}
        assert node.id is None
        assert node.rrf_score is None

    def test_create_full(self):
        nid = uuid.uuid4()
        node = MemoryNode(
            id=nid,
            domain="dce",
            content="Always check ASTM F963 for US toys.",
            memory_type=MemoryType.PATTERN,
            importance=0.8,
            embedding=[0.1, 0.2, 0.3],
            source="op-42",
            metadata={"category": "standards"},
            rrf_score=0.95,
        )
        assert node.id == nid
        assert node.importance == 0.8
        assert len(node.embedding) == 3


class TestMemoryEdge:
    def test_create_edge(self):
        s, t = uuid.uuid4(), uuid.uuid4()
        edge = MemoryEdge(
            source_id=s,
            target_id=t,
            relation=RelationType.UPDATES,
        )
        assert edge.weight == 1.0

    def test_edge_with_weight(self):
        s, t = uuid.uuid4(), uuid.uuid4()
        edge = MemoryEdge(
            source_id=s,
            target_id=t,
            relation=RelationType.CONTRADICTS,
            weight=0.7,
        )
        assert edge.weight == 0.7
