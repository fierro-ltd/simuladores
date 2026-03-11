"""Tests for AnthropicClient cumulative usage tracking."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock


from agent_harness.llm.client import AnthropicClient, TokenUsage


class TestTokenUsageAccumulation:
    """Verify TokenUsage __add__ and AnthropicClient.total_usage."""

    def test_token_usage_add(self):
        a = TokenUsage(input_tokens=10, output_tokens=5, cache_creation_tokens=3, cache_read_tokens=2)
        b = TokenUsage(input_tokens=20, output_tokens=10, cache_creation_tokens=7, cache_read_tokens=8)
        c = a + b
        assert c.input_tokens == 30
        assert c.output_tokens == 15
        assert c.cache_creation_tokens == 10
        assert c.cache_read_tokens == 10

    def test_token_usage_add_identity(self):
        a = TokenUsage(input_tokens=5, output_tokens=3, cache_creation_tokens=1, cache_read_tokens=1)
        zero = TokenUsage()
        assert a + zero == a

    def test_client_starts_with_zero_usage(self):
        client = AnthropicClient(project_id="test-project", region="us-central1")
        assert client.total_usage == TokenUsage()

    async def test_client_accumulates_usage_across_calls(self):
        """Verify that total_usage accumulates across multiple send_message calls."""
        client = AnthropicClient(project_id="test-project", region="us-central1")

        def make_mock_response(input_tokens, output_tokens, cache_creation, cache_read):
            resp = MagicMock()
            resp.content = [MagicMock(type="text", text="hello")]
            resp.stop_reason = "end_turn"
            resp.model = "claude-sonnet-4-6"
            usage = MagicMock()
            usage.input_tokens = input_tokens
            usage.output_tokens = output_tokens
            usage.cache_creation_input_tokens = cache_creation
            usage.cache_read_input_tokens = cache_read
            resp.usage = usage
            return resp

        mock_create = AsyncMock(side_effect=[
            make_mock_response(100, 50, 20, 10),
            make_mock_response(80, 40, 5, 60),
        ])

        # Patch the internal Anthropic client's messages.create method
        client._client.messages.create = mock_create

        prompt = {"system": "You are helpful.", "messages": [{"role": "user", "content": "hi"}]}

        await client.send_message(prompt)
        assert client.total_usage.input_tokens == 100
        assert client.total_usage.cache_read_tokens == 10

        await client.send_message(prompt)
        assert client.total_usage.input_tokens == 180
        assert client.total_usage.output_tokens == 90
        assert client.total_usage.cache_creation_tokens == 25
        assert client.total_usage.cache_read_tokens == 70
