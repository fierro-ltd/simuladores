"""Tests for AnthropicClient, TokenUsage, ToolCall, and MessageResult."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agent_harness.llm.client import (
    AnthropicClient,
    MessageResult,
    TokenUsage,
    ToolCall,
)


# ---------------------------------------------------------------------------
# Sync type tests
# ---------------------------------------------------------------------------


class TestTokenUsage:
    def test_frozen(self):
        u = TokenUsage(input_tokens=10, output_tokens=5)
        with pytest.raises(AttributeError):
            u.input_tokens = 20  # type: ignore[misc]

    def test_defaults(self):
        u = TokenUsage()
        assert u.input_tokens == 0
        assert u.output_tokens == 0
        assert u.cache_creation_tokens == 0
        assert u.cache_read_tokens == 0

    def test_cache_hit_rate_zero_when_no_cache(self):
        u = TokenUsage()
        assert u.cache_hit_rate == 0.0

    def test_cache_hit_rate_all_reads(self):
        u = TokenUsage(cache_read_tokens=100, cache_creation_tokens=0)
        assert u.cache_hit_rate == 1.0

    def test_cache_hit_rate_mixed(self):
        u = TokenUsage(cache_read_tokens=75, cache_creation_tokens=25)
        assert u.cache_hit_rate == 0.75

    def test_addition(self):
        a = TokenUsage(input_tokens=10, output_tokens=5, cache_creation_tokens=2, cache_read_tokens=3)
        b = TokenUsage(input_tokens=20, output_tokens=10, cache_creation_tokens=1, cache_read_tokens=7)
        c = a + b
        assert c.input_tokens == 30
        assert c.output_tokens == 15
        assert c.cache_creation_tokens == 3
        assert c.cache_read_tokens == 10


class TestToolCall:
    def test_frozen(self):
        tc = ToolCall(id="tc_1", name="discover_api", input={"category": "tools"})
        with pytest.raises(AttributeError):
            tc.name = "other"  # type: ignore[misc]

    def test_fields(self):
        tc = ToolCall(id="tc_1", name="discover_api", input={"category": "tools"})
        assert tc.id == "tc_1"
        assert tc.name == "discover_api"
        assert tc.input == {"category": "tools"}


class TestMessageResult:
    def test_frozen(self):
        mr = MessageResult(content="hello", stop_reason="end_turn")
        with pytest.raises(AttributeError):
            mr.content = "bye"  # type: ignore[misc]

    def test_defaults(self):
        mr = MessageResult(content="hi", stop_reason="end_turn")
        assert mr.tool_calls == []
        assert mr.usage == TokenUsage()
        assert mr.model == ""

    def test_with_tool_calls(self):
        tc = ToolCall(id="tc_1", name="test", input={})
        mr = MessageResult(
            content="",
            stop_reason="tool_use",
            tool_calls=[tc],
            usage=TokenUsage(input_tokens=100),
            model="claude-sonnet-4-6",
        )
        assert len(mr.tool_calls) == 1
        assert mr.usage.input_tokens == 100


# ---------------------------------------------------------------------------
# Prompt translation tests
# ---------------------------------------------------------------------------


class TestTranslatePrompt:
    def _make_prompt(self, system_cache: bool = True) -> dict:
        return {
            "system": "You are Santos.",
            "messages": [{"role": "user", "content": "Hello"}],
            "cache_control": {"system_cache": system_cache},
        }

    def test_system_cache_enabled(self):
        prompt = self._make_prompt(system_cache=True)
        result = AnthropicClient._translate_prompt(prompt, "claude-sonnet-4-6", 4096)
        # System should be a list with cache_control
        assert isinstance(result["system"], list)
        assert len(result["system"]) == 1
        block = result["system"][0]
        assert block["type"] == "text"
        assert block["text"] == "You are Santos."
        assert block["cache_control"] == {"type": "ephemeral"}

    def test_system_cache_disabled(self):
        prompt = self._make_prompt(system_cache=False)
        result = AnthropicClient._translate_prompt(prompt, "claude-sonnet-4-6", 4096)
        # System should be plain string
        assert result["system"] == "You are Santos."

    def test_model_and_max_tokens(self):
        prompt = self._make_prompt()
        result = AnthropicClient._translate_prompt(prompt, "claude-sonnet-4-6", 8192)
        assert result["model"] == "claude-sonnet-4-6"
        assert result["max_tokens"] == 8192

    def test_messages_passed_through(self):
        prompt = self._make_prompt()
        result = AnthropicClient._translate_prompt(prompt, "claude-sonnet-4-6", 4096)
        assert result["messages"] == [{"role": "user", "content": "Hello"}]

    def test_tools_included_when_provided(self):
        prompt = self._make_prompt()
        tools = [{"name": "discover_api", "description": "Find APIs", "input_schema": {}}]
        result = AnthropicClient._translate_prompt(prompt, "claude-sonnet-4-6", 4096, tools=tools)
        assert result["tools"] == tools

    def test_tools_absent_when_none(self):
        prompt = self._make_prompt()
        result = AnthropicClient._translate_prompt(prompt, "claude-sonnet-4-6", 4096, tools=None)
        assert "tools" not in result


# ---------------------------------------------------------------------------
# Async mocked tests for send_message
# ---------------------------------------------------------------------------


def _make_text_response(text: str = "Hello world") -> SimpleNamespace:
    """Build a mock Anthropic API response with a text block."""
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason="end_turn",
        usage=SimpleNamespace(
            input_tokens=50,
            output_tokens=10,
            cache_creation_input_tokens=5,
            cache_read_input_tokens=3,
        ),
        model="claude-sonnet-4-6",
    )


def _make_tool_use_response() -> SimpleNamespace:
    """Build a mock Anthropic API response with a tool_use block."""
    return SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="I'll look that up."),
            SimpleNamespace(
                type="tool_use",
                id="toolu_01ABC",
                name="discover_api",
                input={"category": "extraction"},
            ),
        ],
        stop_reason="tool_use",
        usage=SimpleNamespace(
            input_tokens=80,
            output_tokens=25,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        ),
        model="claude-sonnet-4-6",
    )


@pytest.fixture
def mock_client(mocker):
    """AnthropicClient with mocked AsyncAnthropic."""
    client = AnthropicClient(project_id="test-project", region="us-central1")
    mock_create = AsyncMock()
    mocker.patch.object(client._client.messages, "create", mock_create)
    return client, mock_create


class TestSendMessageEndTurn:
    async def test_text_response(self, mock_client):
        client, mock_create = mock_client
        mock_create.return_value = _make_text_response("Analysis complete.")

        prompt = {
            "system": "You are Santos.",
            "messages": [{"role": "user", "content": "Analyze this."}],
            "cache_control": {"system_cache": True},
        }
        result = await client.send_message(prompt)

        assert result.content == "Analysis complete."
        assert result.stop_reason == "end_turn"
        assert result.tool_calls == []
        assert result.usage.input_tokens == 50
        assert result.usage.output_tokens == 10
        assert result.usage.cache_creation_tokens == 5
        assert result.usage.cache_read_tokens == 3
        assert result.model == "claude-sonnet-4-6"

    async def test_uses_default_model(self, mock_client):
        client, mock_create = mock_client
        mock_create.return_value = _make_text_response()

        prompt = {
            "system": "Test",
            "messages": [{"role": "user", "content": "Hi"}],
            "cache_control": {"system_cache": False},
        }
        await client.send_message(prompt)

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4-6"

    async def test_model_override(self, mock_client):
        client, mock_create = mock_client
        mock_create.return_value = _make_text_response()

        prompt = {
            "system": "Test",
            "messages": [{"role": "user", "content": "Hi"}],
            "cache_control": {"system_cache": False},
        }
        await client.send_message(prompt, model="claude-sonnet-4-6")

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4-6"


class TestSendMessageToolUse:
    async def test_tool_calls_extracted(self, mock_client):
        client, mock_create = mock_client
        mock_create.return_value = _make_tool_use_response()

        prompt = {
            "system": "You are Lamponne.",
            "messages": [{"role": "user", "content": "Find extraction APIs."}],
            "cache_control": {"system_cache": True},
        }
        tools = [{"name": "discover_api", "description": "Find APIs", "input_schema": {}}]
        result = await client.send_message(prompt, tools=tools)

        assert result.stop_reason == "tool_use"
        assert result.content == "I'll look that up."
        assert len(result.tool_calls) == 1
        tc = result.tool_calls[0]
        assert tc.id == "toolu_01ABC"
        assert tc.name == "discover_api"
        assert tc.input == {"category": "extraction"}
        assert result.usage.input_tokens == 80
