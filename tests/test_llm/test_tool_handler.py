"""Tests for ToolHandler tool-use loop."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agent_harness.llm.client import AnthropicClient, MessageResult, TokenUsage, ToolCall
from agent_harness.llm.tool_handler import ToolHandler, ToolLoopResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _prompt() -> dict:
    return {
        "system": "You are Lamponne.",
        "messages": [{"role": "user", "content": "Execute the plan."}],
        "cache_control": {"system_cache": True},
    }


TOOLS = [
    {
        "name": "discover_api",
        "description": "Discover available APIs",
        "input_schema": {
            "type": "object",
            "properties": {"category": {"type": "string"}},
        },
    }
]

USAGE = TokenUsage(input_tokens=50, output_tokens=10)


def _text_result(content: str = "Done.") -> MessageResult:
    return MessageResult(
        content=content,
        stop_reason="end_turn",
        tool_calls=[],
        usage=USAGE,
        model="claude-sonnet-4-6",
    )


def _tool_use_result(
    tool_name: str = "discover_api",
    tool_input: dict | None = None,
    tool_id: str = "toolu_01",
    content: str = "",
) -> MessageResult:
    return MessageResult(
        content=content,
        stop_reason="tool_use",
        tool_calls=[
            ToolCall(id=tool_id, name=tool_name, input=tool_input or {"category": "extraction"})
        ],
        usage=USAGE,
        model="claude-sonnet-4-6",
    )


# ---------------------------------------------------------------------------
# Type tests
# ---------------------------------------------------------------------------


class TestToolLoopResultType:
    def test_frozen(self):
        r = ToolLoopResult(final_content="ok", turns=1)
        with pytest.raises(AttributeError):
            r.turns = 2  # type: ignore[misc]

    def test_defaults(self):
        r = ToolLoopResult(final_content="ok", turns=1)
        assert r.tool_calls_made == []
        assert r.tool_errors == 0
        assert r.max_turns_reached is False
        assert r.total_usage == TokenUsage()


# ---------------------------------------------------------------------------
# Async loop tests
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_anthropic(mocker):
    """Return an AnthropicClient with mocked send_message."""
    client = AnthropicClient(project_id="test-project", region="us-central1")
    mock_send = AsyncMock()
    mocker.patch.object(client, "send_message", mock_send)
    return client, mock_send


class TestToolLoopNoTools:
    async def test_returns_immediately(self, mock_anthropic):
        client, mock_send = mock_anthropic
        mock_send.return_value = _text_result("All done.")

        handler = ToolHandler(client, {})
        result = await handler.run_loop(_prompt(), "claude-sonnet-4-6", TOOLS)

        assert result.final_content == "All done."
        assert result.turns == 1
        assert result.tool_calls_made == []
        assert result.tool_errors == 0
        assert result.max_turns_reached is False
        assert result.total_usage == USAGE


class TestToolLoopOneToolCall:
    async def test_calls_tool_then_responds(self, mock_anthropic):
        client, mock_send = mock_anthropic

        async def fake_discover(inp: dict) -> str:
            return '["extract_text", "extract_table"]'

        mock_send.side_effect = [
            _tool_use_result("discover_api", {"category": "extraction"}, "toolu_01"),
            _text_result("Found 2 extraction APIs."),
        ]

        handler = ToolHandler(client, {"discover_api": fake_discover})
        result = await handler.run_loop(_prompt(), "claude-sonnet-4-6", TOOLS)

        assert result.final_content == "Found 2 extraction APIs."
        assert result.turns == 2
        assert len(result.tool_calls_made) == 1
        assert result.tool_calls_made[0].name == "discover_api"
        assert result.tool_errors == 0
        assert result.max_turns_reached is False
        # Usage should be sum of both turns
        assert result.total_usage.input_tokens == 100
        assert result.total_usage.output_tokens == 20

    async def test_tool_handler_receives_correct_input(self, mock_anthropic):
        client, mock_send = mock_anthropic
        received_inputs: list[dict] = []

        async def capture_discover(inp: dict) -> str:
            received_inputs.append(inp)
            return "ok"

        mock_send.side_effect = [
            _tool_use_result("discover_api", {"category": "navigation"}, "toolu_02"),
            _text_result("Done."),
        ]

        handler = ToolHandler(client, {"discover_api": capture_discover})
        await handler.run_loop(_prompt(), "claude-sonnet-4-6", TOOLS)

        assert len(received_inputs) == 1
        assert received_inputs[0] == {"category": "navigation"}


class TestToolLoopMaxTurnsExceeded:
    async def test_max_turns_flag(self, mock_anthropic):
        client, mock_send = mock_anthropic
        # Always return tool_use — never stops
        mock_send.return_value = _tool_use_result()

        async def noop_handler(inp: dict) -> str:
            return "ok"

        handler = ToolHandler(client, {"discover_api": noop_handler})
        result = await handler.run_loop(_prompt(), "claude-sonnet-4-6", TOOLS, max_turns=3)

        assert result.max_turns_reached is True
        assert result.turns == 3
        assert len(result.tool_calls_made) == 3


class TestToolLoopUnknownTool:
    async def test_error_result_for_unknown(self, mock_anthropic):
        client, mock_send = mock_anthropic

        mock_send.side_effect = [
            _tool_use_result("nonexistent_tool", {}, "toolu_bad"),
            _text_result("Proceeding without that tool."),
        ]

        handler = ToolHandler(client, {})  # No handlers registered
        result = await handler.run_loop(_prompt(), "claude-sonnet-4-6", TOOLS)

        assert result.tool_errors == 1
        assert result.turns == 2
        assert result.final_content == "Proceeding without that tool."
        assert len(result.tool_calls_made) == 1
        assert result.tool_calls_made[0].name == "nonexistent_tool"

    async def test_tool_exception_counted(self, mock_anthropic):
        client, mock_send = mock_anthropic

        async def failing_handler(inp: dict) -> str:
            raise RuntimeError("Connection failed")

        mock_send.side_effect = [
            _tool_use_result("discover_api", {}, "toolu_err"),
            _text_result("Recovered."),
        ]

        handler = ToolHandler(client, {"discover_api": failing_handler})
        result = await handler.run_loop(_prompt(), "claude-sonnet-4-6", TOOLS)

        assert result.tool_errors == 1
        assert result.turns == 2
        assert result.final_content == "Recovered."
