"""Tests for post-job learning pattern extraction."""

import pytest

from agent_harness.memory.embeddings import FakeEmbeddingClient
from agent_harness.memory.graph import MemoryType
from agent_harness.memory.graph_store import InMemoryGraphStore
from agent_harness.activities.post_job import extract_patterns


class TestExtractPatterns:
    @pytest.fixture
    def store(self):
        return InMemoryGraphStore(embedder=FakeEmbeddingClient(dimensions=8))

    @pytest.mark.asyncio
    async def test_extracts_from_progress(self, store):
        progress = (
            "## PLAN — santos\n\n"
            "Santos planned 3 steps for operativo op-1.\n\n"
            "## INVESTIGATE — medina\n\n"
            "Medina investigated doc.pdf. Risk: none.\n\n"
            "## QA_REVIEW — santos\n\n"
            "Santos QA: 5 checks, status=COMPLETED.\n\n"
        )
        count = await extract_patterns(
            store=store,
            domain="dce",
            operativo_id="op-1",
            session_progress=progress,
        )
        assert count >= 1
        nodes = await store.list_by_domain("dce")
        assert len(nodes) >= 1
        assert all(n.source == "op-1" for n in nodes)

    @pytest.mark.asyncio
    async def test_empty_progress_extracts_nothing(self, store):
        count = await extract_patterns(
            store=store,
            domain="dce",
            operativo_id="op-2",
            session_progress="",
        )
        assert count == 0

    @pytest.mark.asyncio
    async def test_patterns_have_correct_type(self, store):
        progress = "## QA_REVIEW — santos\n\nSantos QA: 3 checks, status=NEEDS_REVIEW.\n\n"
        await extract_patterns(
            store=store,
            domain="dce",
            operativo_id="op-3",
            session_progress=progress,
        )
        nodes = await store.list_by_domain("dce")
        # QA issues should be stored as ERROR type
        error_nodes = [n for n in nodes if n.memory_type == MemoryType.ERROR]
        assert len(error_nodes) >= 1

    @pytest.mark.asyncio
    async def test_successful_completion_stored_as_pattern(self, store):
        progress = "## QA_REVIEW — santos\n\nSantos QA: 5 checks, status=COMPLETED.\n\n"
        await extract_patterns(
            store=store,
            domain="dce",
            operativo_id="op-4",
            session_progress=progress,
        )
        nodes = await store.list_by_domain("dce")
        pattern_nodes = [n for n in nodes if n.memory_type == MemoryType.PATTERN]
        assert len(pattern_nodes) >= 1


class TestPostJobLearnActivity:
    """Tests for the post_job_learn Temporal activity."""

    @pytest.mark.asyncio
    async def test_post_job_learn_extracts_patterns(self):
        """Activity wires through to extract_patterns and returns real count."""
        from agent_harness.activities.implementations import post_job_learn
        from agent_harness.activities.post_job import PostJobInput

        progress = (
            "## PLAN — santos\n\n"
            "Santos planned 3 steps for operativo op-100.\n\n"
            "## INVESTIGATE — medina\n\n"
            "Medina investigated doc.pdf. Risk: none.\n\n"
            "## QA_REVIEW — santos\n\n"
            "Santos QA: 5 checks, status=COMPLETED.\n\n"
        )
        input_data = PostJobInput(
            operativo_id="op-100",
            domain="dce",
            session_progress=progress,
        )
        result = await post_job_learn(input_data)
        assert result.operativo_id == "op-100"
        assert result.patterns_extracted >= 1
        assert result.archived is True

    @pytest.mark.asyncio
    async def test_post_job_learn_empty_progress(self):
        """Activity returns 0 patterns for empty progress."""
        from agent_harness.activities.implementations import post_job_learn
        from agent_harness.activities.post_job import PostJobInput

        input_data = PostJobInput(
            operativo_id="op-101",
            domain="dce",
            session_progress="",
        )
        result = await post_job_learn(input_data)
        assert result.patterns_extracted == 0
        assert result.archived is True

    @pytest.mark.asyncio
    async def test_post_job_learn_returns_count(self):
        """Activity returns actual count matching number of parsed sections."""
        from agent_harness.activities.implementations import post_job_learn
        from agent_harness.activities.post_job import PostJobInput

        # Two sections
        progress = (
            "## PLAN — santos\n\n"
            "Santos planned 2 steps.\n\n"
            "## EXECUTE — lamponne\n\n"
            "Lamponne executed the plan.\n\n"
        )
        input_data = PostJobInput(
            operativo_id="op-102",
            domain="dce",
            session_progress=progress,
        )
        result = await post_job_learn(input_data)
        assert result.patterns_extracted == 2
