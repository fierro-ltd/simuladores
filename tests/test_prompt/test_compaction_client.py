"""Tests for compaction client."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_harness.prompt.compaction_client import (
    COMPACTION_SYSTEM_PROMPT,
    CompactionClient,
    CompactionRequest,
    CompactionResult,
    _RECENT_MESSAGES_KEEP,
)
from agent_harness.prompt.compactor import CompactionConfig, CompactionStrategy


class TestCompactionRequest:
    def test_defaults(self):
        req = CompactionRequest()
        assert req.model == "compact-2026-01-12"
        assert req.system_prompt == ""
        assert req.messages == []
        assert req.protected_content == []

    def test_with_values(self):
        req = CompactionRequest(
            system_prompt="You are Santos.",
            messages=[{"role": "user", "content": "hello"}],
            protected_content=["input_snapshot"],
        )
        assert req.system_prompt == "You are Santos."
        assert len(req.messages) == 1
        assert "input_snapshot" in req.protected_content

    def test_frozen(self):
        req = CompactionRequest()
        with pytest.raises(AttributeError):
            req.model = "different"


class TestCompactionResult:
    def test_defaults(self):
        result = CompactionResult()
        assert result.tokens_before == 0
        assert result.tokens_after == 0
        assert result.strategy_used == CompactionStrategy.ANTHROPIC_API

    def test_with_values(self):
        result = CompactionResult(
            compacted_messages=[{"role": "user", "content": "summary"}],
            tokens_before=10000,
            tokens_after=6000,
            strategy_used=CompactionStrategy.SESSION_BRIDGE,
            protected_fields_preserved=2,
        )
        assert result.tokens_before == 10000
        assert result.tokens_after == 6000
        assert result.protected_fields_preserved == 2


class TestCompactionClient:
    def test_default_config(self):
        client = CompactionClient()
        assert client.config.threshold == 0.8
        assert client.config.max_tokens == 128_000

    def test_needs_compaction_below_threshold(self):
        client = CompactionClient()
        assert client.needs_compaction(50_000) is False

    def test_needs_compaction_at_threshold(self):
        client = CompactionClient()
        assert client.needs_compaction(102_400) is True  # 80% of 128k

    def test_needs_compaction_above_threshold(self):
        client = CompactionClient()
        assert client.needs_compaction(120_000) is True

    def test_custom_threshold(self):
        config = CompactionConfig(threshold=0.5, max_tokens=100_000)
        client = CompactionClient(config)
        assert client.needs_compaction(50_000) is True
        assert client.needs_compaction(49_999) is False

    def test_build_request_basic(self):
        client = CompactionClient()
        req = client.build_request(
            system_prompt="system",
            messages=[{"role": "user", "content": "hi"}],
        )
        assert isinstance(req, CompactionRequest)
        assert req.system_prompt == "system"
        assert len(req.messages) == 1
        assert req.protected_content == []

    def test_build_request_with_protection(self):
        client = CompactionClient()
        req = client.build_request(
            system_prompt="system",
            messages=[],
            protected_content=["input_snapshot"],
        )
        assert "input_snapshot" in req.protected_content

    def test_build_request_merges_config_protected(self):
        config = CompactionConfig(protected_fields=["config_field"])
        client = CompactionClient(config)
        req = client.build_request(
            system_prompt="system",
            messages=[],
            protected_content=["call_field"],
        )
        assert "call_field" in req.protected_content
        assert "config_field" in req.protected_content

    def test_estimate_savings(self):
        client = CompactionClient()
        assert client.estimate_savings(10_000) == 4_000

    def test_estimate_savings_zero(self):
        client = CompactionClient()
        assert client.estimate_savings(0) == 0


class TestCompactMethod:
    """Tests for CompactionClient.compact() async method."""

    def _make_mock_client(self, summary_text: str = "Compacted summary.") -> AsyncMock:
        """Create a mock AsyncAnthropicVertex client."""
        mock_block = MagicMock()
        mock_block.text = summary_text

        mock_response = MagicMock()
        mock_response.content = [mock_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        return mock_client

    @pytest.mark.asyncio
    async def test_compact_returns_compaction_result(self):
        mock_client = self._make_mock_client("Summary of conversation.")
        client = CompactionClient()
        messages = [{"role": "user", "content": f"message {i}"} for i in range(20)]

        result = await client.compact(
            anthropic_client=mock_client,
            system_prompt="You are Santos.",
            messages=messages,
            operativo_id="op-123",
        )

        assert isinstance(result, CompactionResult)
        assert result.strategy_used == CompactionStrategy.ANTHROPIC_API

    @pytest.mark.asyncio
    async def test_compact_calls_anthropic_api(self):
        mock_client = self._make_mock_client()
        client = CompactionClient()
        messages = [{"role": "user", "content": "hello"}]

        await client.compact(
            anthropic_client=mock_client,
            system_prompt="system",
            messages=messages,
            operativo_id="op-456",
        )

        mock_client.messages.create.assert_awaited_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "compact-2026-01-12"
        assert call_kwargs["max_tokens"] == 4096
        assert "op-456" in call_kwargs["system"]
        assert COMPACTION_SYSTEM_PROMPT in call_kwargs["system"]
        assert call_kwargs["messages"] == messages

    @pytest.mark.asyncio
    async def test_compact_builds_summary_plus_recent(self):
        mock_client = self._make_mock_client("Brief summary.")
        client = CompactionClient()
        messages = [{"role": "user", "content": f"msg-{i}"} for i in range(25)]

        result = await client.compact(
            anthropic_client=mock_client,
            system_prompt="system",
            messages=messages,
            operativo_id="op-789",
        )

        # First message is the summary
        assert result.compacted_messages[0]["role"] == "assistant"
        assert result.compacted_messages[0]["content"] == "Brief summary."
        # Then last 10 recent messages
        assert len(result.compacted_messages) == 1 + _RECENT_MESSAGES_KEEP
        assert result.compacted_messages[-1]["content"] == "msg-24"

    @pytest.mark.asyncio
    async def test_compact_short_conversation_keeps_all(self):
        mock_client = self._make_mock_client("Short summary.")
        client = CompactionClient()
        messages = [{"role": "user", "content": f"msg-{i}"} for i in range(5)]

        result = await client.compact(
            anthropic_client=mock_client,
            system_prompt="system",
            messages=messages,
            operativo_id="op-short",
        )

        # summary + all 5 original messages
        assert len(result.compacted_messages) == 1 + 5

    @pytest.mark.asyncio
    async def test_compact_token_counts(self):
        mock_client = self._make_mock_client("sum")
        client = CompactionClient()
        messages = [{"role": "user", "content": "abcdef"}] * 20

        result = await client.compact(
            anthropic_client=mock_client,
            system_prompt="system",
            messages=messages,
            operativo_id="op-tok",
        )

        assert result.tokens_before == 20 * 6  # 20 messages * 6 chars each
        assert result.tokens_after > 0
        assert result.tokens_after < result.tokens_before

    @pytest.mark.asyncio
    async def test_compact_preserves_protected_field_count(self):
        config = CompactionConfig(protected_fields=["input_snapshot", "plan"])
        mock_client = self._make_mock_client("summary")
        client = CompactionClient(config)
        messages = [{"role": "user", "content": "hi"}]

        result = await client.compact(
            anthropic_client=mock_client,
            system_prompt="system",
            messages=messages,
            operativo_id="op-prot",
        )

        assert result.protected_fields_preserved == 2
