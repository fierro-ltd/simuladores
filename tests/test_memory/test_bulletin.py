"""Tests for Cortex Bulletin types and generation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_harness.memory.bulletin import Bulletin, BulletinConfig, generate_bulletin
from agent_harness.llm.client import MessageResult, TokenUsage


# -- Task 1: Bulletin types --------------------------------------------------


class TestBulletinConfig:
    def test_defaults(self):
        config = BulletinConfig()
        assert config.interval_minutes == 60
        assert config.max_patterns == 20
        assert config.max_tokens == 500
        assert config.model == "claude-sonnet-4-6"
        assert config.domain == "dce"

    def test_custom_values(self):
        config = BulletinConfig(
            interval_minutes=30,
            max_patterns=10,
            max_tokens=200,
            model="claude-sonnet-4-6",
            domain="has",
        )
        assert config.interval_minutes == 30
        assert config.max_patterns == 10
        assert config.max_tokens == 200
        assert config.model == "claude-sonnet-4-6"
        assert config.domain == "has"

    def test_frozen(self):
        config = BulletinConfig()
        with pytest.raises(AttributeError):
            config.domain = "other"  # type: ignore[misc]


class TestBulletin:
    def test_creation(self):
        b = Bulletin(
            domain="dce",
            summary="Toys require ASTM F963.",
            pattern_count=5,
            generated_at="2026-02-22T10:00:00+00:00",
        )
        assert b.domain == "dce"
        assert b.summary == "Toys require ASTM F963."
        assert b.pattern_count == 5

    def test_as_pattern_string(self):
        b = Bulletin(
            domain="dce",
            summary="Key insight here.",
            pattern_count=3,
            generated_at="2026-02-22T10:00:00+00:00",
        )
        assert b.as_pattern_string() == "[bulletin] Key insight here."

    def test_as_pattern_string_empty(self):
        b = Bulletin(
            domain="dce",
            summary="",
            pattern_count=0,
            generated_at="2026-02-22T10:00:00+00:00",
        )
        assert b.as_pattern_string() == ""

    def test_is_stale_true(self):
        generated = datetime(2026, 2, 22, 10, 0, 0, tzinfo=timezone.utc)
        now = generated + timedelta(minutes=61)
        b = Bulletin(
            domain="dce",
            summary="test",
            pattern_count=1,
            generated_at=generated.isoformat(),
        )
        assert b.is_stale(now, max_age_minutes=60) is True

    def test_is_stale_false(self):
        generated = datetime(2026, 2, 22, 10, 0, 0, tzinfo=timezone.utc)
        now = generated + timedelta(minutes=30)
        b = Bulletin(
            domain="dce",
            summary="test",
            pattern_count=1,
            generated_at=generated.isoformat(),
        )
        assert b.is_stale(now, max_age_minutes=60) is False

    def test_is_stale_custom_max_age(self):
        generated = datetime(2026, 2, 22, 10, 0, 0, tzinfo=timezone.utc)
        now = generated + timedelta(minutes=31)
        b = Bulletin(
            domain="dce",
            summary="test",
            pattern_count=1,
            generated_at=generated.isoformat(),
        )
        assert b.is_stale(now, max_age_minutes=30) is True

    def test_frozen(self):
        b = Bulletin(
            domain="dce",
            summary="test",
            pattern_count=1,
            generated_at="2026-02-22T10:00:00+00:00",
        )
        with pytest.raises(AttributeError):
            b.summary = "changed"  # type: ignore[misc]


# -- Task 2: Bulletin generator -----------------------------------------------


class TestGenerateBulletin:
    @pytest.mark.asyncio
    async def test_generates_bulletin_from_patterns(self):
        """With patterns in the store, should call LLM and return summary."""
        mock_client = AsyncMock()
        mock_client.send_message.return_value = MessageResult(
            content="compliance documents need ASTM F963 and EN71 testing.",
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=100, output_tokens=20),
            model="claude-sonnet-4-6",
        )

        mock_recall = MagicMock(spec=True)
        mock_recall.__class__ = type("MemoryRecall", (), {})
        # We need a real MemoryRecall for the isinstance check
        from agent_harness.memory.recall import MemoryRecall
        from agent_harness.memory.graph_store import InMemoryGraphStore
        from agent_harness.memory.embeddings import FakeEmbeddingClient

        store = InMemoryGraphStore(FakeEmbeddingClient())
        recall = MemoryRecall(store)
        # Monkey-patch retrieve_patterns to return our test data
        recall.retrieve_patterns = AsyncMock(
            return_value=[
                "[fact] Toys require ASTM F963.",
                "[pattern] EN71 applies to EU-bound toys.",
            ]
        )

        config = BulletinConfig(domain="dce")
        bulletin = await generate_bulletin(mock_client, recall, config)

        assert bulletin.domain == "dce"
        assert bulletin.summary == "compliance documents need ASTM F963 and EN71 testing."
        assert bulletin.pattern_count == 2
        assert bulletin.generated_at  # non-empty ISO string
        mock_client.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_store_returns_empty_bulletin(self):
        """With no patterns, should return empty bulletin without calling LLM."""
        mock_client = AsyncMock()

        from agent_harness.memory.recall import MemoryRecall
        from agent_harness.memory.graph_store import InMemoryGraphStore
        from agent_harness.memory.embeddings import FakeEmbeddingClient

        store = InMemoryGraphStore(FakeEmbeddingClient())
        recall = MemoryRecall(store)
        recall.retrieve_patterns = AsyncMock(return_value=[])

        config = BulletinConfig(domain="dce")
        bulletin = await generate_bulletin(mock_client, recall, config)

        assert bulletin.summary == ""
        assert bulletin.pattern_count == 0
        mock_client.send_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_uses_sonnet_model(self):
        """Should pass the configured model to client.send_message."""
        mock_client = AsyncMock()
        mock_client.send_message.return_value = MessageResult(
            content="Summary.",
            stop_reason="end_turn",
            usage=TokenUsage(),
            model="claude-sonnet-4-6",
        )

        from agent_harness.memory.recall import MemoryRecall
        from agent_harness.memory.graph_store import InMemoryGraphStore
        from agent_harness.memory.embeddings import FakeEmbeddingClient

        store = InMemoryGraphStore(FakeEmbeddingClient())
        recall = MemoryRecall(store)
        recall.retrieve_patterns = AsyncMock(
            return_value=["[fact] Test pattern."]
        )

        config = BulletinConfig(model="claude-sonnet-4-6", domain="dce")
        await generate_bulletin(mock_client, recall, config)

        call_kwargs = mock_client.send_message.call_args
        assert call_kwargs.kwargs["model"] == "claude-sonnet-4-6"


# -- Task 7: Module exports ---------------------------------------------------


class TestModuleExports:
    def test_bulletin_importable_from_memory(self):
        from agent_harness.memory import Bulletin, BulletinConfig, generate_bulletin, InMemoryBulletinStore

        assert Bulletin is not None
        assert BulletinConfig is not None
        assert generate_bulletin is not None
        assert InMemoryBulletinStore is not None
