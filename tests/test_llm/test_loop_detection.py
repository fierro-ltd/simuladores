"""Tests for ResourceEditTracker loop detection."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agent_harness.llm.client import AnthropicClient, MessageResult, TokenUsage, ToolCall
from agent_harness.llm.loop_detection import ResourceEditTracker
from agent_harness.llm.tool_handler import ToolHandler, ToolLoopResult


# ---------------------------------------------------------------------------
# ResourceEditTracker unit tests
# ---------------------------------------------------------------------------


class TestResourceEditTrackerBelowThreshold:
    def test_returns_none_below_threshold(self):
        tracker = ResourceEditTracker(threshold=3)
        assert tracker.record("discover_api", {}) is None
        assert tracker.record("discover_api", {}) is None

    def test_returns_none_for_different_tools(self):
        tracker = ResourceEditTracker(threshold=2)
        assert tracker.record("discover_api", {}) is None
        assert tracker.record("execute_api", {"operation": "extract_text"}) is None


class TestResourceEditTrackerAtThreshold:
    def test_returns_guidance_at_threshold(self):
        tracker = ResourceEditTracker(threshold=3)
        assert tracker.record("discover_api", {}) is None
        assert tracker.record("discover_api", {}) is None
        guidance = tracker.record("discover_api", {})
        assert guidance is not None
        assert "[HARNESS]" in guidance
        assert "discover_api" in guidance
        assert "3 times" in guidance

    def test_returns_guidance_above_threshold(self):
        tracker = ResourceEditTracker(threshold=2)
        tracker.record("discover_api", {})
        tracker.record("discover_api", {})
        guidance = tracker.record("discover_api", {})
        assert guidance is not None
        assert "3 times" in guidance


class TestResourceEditTrackerExtractResource:
    def test_execute_api_uses_operation(self):
        tracker = ResourceEditTracker(threshold=2)
        tracker.record("execute_api", {"operation": "extract_text"})
        guidance = tracker.record("execute_api", {"operation": "extract_text"})
        assert guidance is not None
        assert "extract_text" in guidance

    def test_execute_api_different_operations_separate(self):
        tracker = ResourceEditTracker(threshold=2)
        assert tracker.record("execute_api", {"operation": "extract_text"}) is None
        assert tracker.record("execute_api", {"operation": "validate_cert"}) is None

    def test_non_execute_api_uses_tool_name(self):
        tracker = ResourceEditTracker(threshold=2)
        tracker.record("discover_api", {"category": "a"})
        guidance = tracker.record("discover_api", {"category": "b"})
        assert guidance is not None
        assert "discover_api" in guidance


class TestResourceEditTrackerCounts:
    def test_counts_property(self):
        tracker = ResourceEditTracker()
        tracker.record("discover_api", {})
        tracker.record("discover_api", {})
        tracker.record("execute_api", {"operation": "op1"})
        counts = tracker.counts
        assert counts == {"discover_api": 2, "op1": 1}

    def test_counts_returns_copy(self):
        tracker = ResourceEditTracker()
        tracker.record("discover_api", {})
        counts = tracker.counts
        counts["discover_api"] = 999
        assert tracker.counts["discover_api"] == 1


class TestResourceEditTrackerReset:
    def test_reset_clears_counters(self):
        tracker = ResourceEditTracker(threshold=2)
        tracker.record("discover_api", {})
        tracker.record("discover_api", {})
        tracker.reset()
        assert tracker.counts == {}
        # Should not trigger guidance after reset
        assert tracker.record("discover_api", {}) is None


# ---------------------------------------------------------------------------
# ToolHandler integration tests for loop detection
# ---------------------------------------------------------------------------

USAGE = TokenUsage(input_tokens=50, output_tokens=10)


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


@pytest.fixture
def mock_anthropic(mocker):
    client = AnthropicClient(project_id="test-project", region="us-central1")
    mock_send = AsyncMock()
    mocker.patch.object(client, "send_message", mock_send)
    return client, mock_send


class TestToolHandlerLoopDetectionEnabled:
    async def test_loop_warnings_count_in_result(self, mock_anthropic):
        """When same tool called >= threshold times, loop_warnings increments."""
        client, mock_send = mock_anthropic
        threshold = 2

        async def noop_handler(inp: dict) -> str:
            return "ok"

        # 4 tool calls then done: calls 1 is fine, call 2+ trigger warnings
        side_effects = [
            _tool_use_result("discover_api", {"category": "a"}, f"toolu_{i:02d}")
            for i in range(4)
        ]
        side_effects.append(_text_result("Finished."))
        mock_send.side_effect = side_effects

        handler = ToolHandler(client, {"discover_api": noop_handler})
        result = await handler.run_loop(
            _prompt(), "claude-sonnet-4-6", TOOLS,
            max_turns=10, loop_threshold=threshold,
        )

        assert result.final_content == "Finished."
        # Calls: 1 (count=1, no warn), 2 (count=2, warn), 3 (count=3, warn), 4 (count=4, warn)
        assert result.loop_warnings == 3

    async def test_guidance_appended_to_tool_result(self, mock_anthropic):
        """Guidance text is appended to the tool result content."""
        client, mock_send = mock_anthropic

        outputs: list[str] = []

        async def capturing_handler(inp: dict) -> str:
            return "tool-output"

        side_effects = [
            _tool_use_result("discover_api", {}, f"toolu_{i:02d}")
            for i in range(3)
        ]
        side_effects.append(_text_result("Done."))
        mock_send.side_effect = side_effects

        handler = ToolHandler(client, {"discover_api": capturing_handler})
        result = await handler.run_loop(
            _prompt(), "claude-sonnet-4-6", TOOLS,
            max_turns=10, loop_threshold=2,
        )

        # Check the messages sent back contain guidance after threshold
        # The 2nd tool call (index 1) should have guidance appended
        # Messages: user, [assistant, user(tool_result)]x3, assistant(final)
        messages = mock_send.call_args_list[-1][0][0]["messages"]
        # Find user messages with tool_results
        tool_result_messages = [
            m for m in messages if m["role"] == "user" and isinstance(m["content"], list)
        ]
        # First tool result: no guidance
        assert "[HARNESS]" not in tool_result_messages[0]["content"][0]["content"]
        # Second tool result: has guidance
        assert "[HARNESS]" in tool_result_messages[1]["content"][0]["content"]


class TestToolHandlerLoopDetectionDisabled:
    async def test_no_warnings_when_disabled(self, mock_anthropic):
        client, mock_send = mock_anthropic

        async def noop_handler(inp: dict) -> str:
            return "ok"

        side_effects = [
            _tool_use_result("discover_api", {}, f"toolu_{i:02d}")
            for i in range(5)
        ]
        side_effects.append(_text_result("Done."))
        mock_send.side_effect = side_effects

        handler = ToolHandler(client, {"discover_api": noop_handler})
        result = await handler.run_loop(
            _prompt(), "claude-sonnet-4-6", TOOLS,
            max_turns=10, enable_loop_detection=False, loop_threshold=2,
        )

        assert result.loop_warnings == 0


class TestToolLoopResultLoopWarnings:
    def test_default_zero(self):
        r = ToolLoopResult(final_content="ok", turns=1)
        assert r.loop_warnings == 0

    def test_frozen_field(self):
        r = ToolLoopResult(final_content="ok", turns=1, loop_warnings=3)
        assert r.loop_warnings == 3
        with pytest.raises(AttributeError):
            r.loop_warnings = 0  # type: ignore[misc]
