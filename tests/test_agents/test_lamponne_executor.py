"""Tests for LamponneExecutor."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from agent_harness.agents.lamponne import (
    LAMPONNE_SYSTEM_IDENTITY,
    LAMPONNE_TOOLS,
    LamponneExecutor,
)
from agent_harness.agents.base import AGENT_MODELS
from agent_harness.llm.client import AnthropicClient, TokenUsage
from agent_harness.llm.tool_handler import ToolHandler, ToolLoopResult


class TestLamponneExecutorInit:
    def test_uses_sonnet_model(self):
        ex = LamponneExecutor(domain="dce")
        assert ex.config.model == AGENT_MODELS["lamponne"]
        assert ex.config.model == "claude-sonnet-4-6"

    def test_uses_lamponne_identity(self):
        ex = LamponneExecutor(domain="dce")
        assert ex.config.system_identity == LAMPONNE_SYSTEM_IDENTITY

    def test_stores_domain(self):
        ex = LamponneExecutor(domain="dce")
        assert ex.config.domain == "dce"

    def test_default_max_turns(self):
        ex = LamponneExecutor(domain="dce")
        assert ex.config.max_turns == 10

    def test_custom_max_turns(self):
        ex = LamponneExecutor(domain="dce", max_turns=5)
        assert ex.config.max_turns == 5

    def test_agent_name_is_lamponne(self):
        ex = LamponneExecutor(domain="dce")
        assert ex.config.name == "lamponne"


class TestLamponneExecute:
    @pytest.mark.asyncio
    async def test_returns_final_content(self):
        ex = LamponneExecutor(domain="dce")

        tool_handler = MagicMock(spec=ToolHandler)
        tool_handler.run_loop = AsyncMock(return_value=ToolLoopResult(
            final_content="Execution complete: all 3 steps succeeded.",
            turns=5,
            tool_calls_made=[],
            tool_errors=0,
            max_turns_reached=False,
            total_usage=TokenUsage(),
        ))
        client = MagicMock(spec=AnthropicClient)

        result = await ex.execute(
            client=client,
            tool_handler=tool_handler,
            operativo_id="op-456",
            plan_json='{"steps": [{"agent": "lamponne", "action": "validate"}]}',
            domain_memory="# DCE Domain",
        )

        assert result == "Execution complete: all 3 steps succeeded."

    @pytest.mark.asyncio
    async def test_calls_tool_handler_with_lamponne_tools(self):
        ex = LamponneExecutor(domain="dce")

        tool_handler = MagicMock(spec=ToolHandler)
        tool_handler.run_loop = AsyncMock(return_value=ToolLoopResult(
            final_content="done",
            turns=1,
            total_usage=TokenUsage(),
        ))
        client = MagicMock(spec=AnthropicClient)

        await ex.execute(
            client=client,
            tool_handler=tool_handler,
            operativo_id="op-1",
            plan_json="{}",
            domain_memory="",
        )

        tool_handler.run_loop.assert_called_once()
        call_kwargs = tool_handler.run_loop.call_args
        assert call_kwargs.kwargs["tools"] == LAMPONNE_TOOLS
        assert call_kwargs.kwargs["model"] == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_respects_max_turns(self):
        ex = LamponneExecutor(domain="dce", max_turns=7)

        tool_handler = MagicMock(spec=ToolHandler)
        tool_handler.run_loop = AsyncMock(return_value=ToolLoopResult(
            final_content="done",
            turns=1,
            total_usage=TokenUsage(),
        ))
        client = MagicMock(spec=AnthropicClient)

        await ex.execute(
            client=client,
            tool_handler=tool_handler,
            operativo_id="op-1",
            plan_json="{}",
            domain_memory="",
        )

        call_kwargs = tool_handler.run_loop.call_args
        assert call_kwargs.kwargs["max_turns"] == 7

    @pytest.mark.asyncio
    async def test_includes_plan_in_prompt(self):
        ex = LamponneExecutor(domain="dce")

        tool_handler = MagicMock(spec=ToolHandler)
        tool_handler.run_loop = AsyncMock(return_value=ToolLoopResult(
            final_content="done",
            turns=1,
            total_usage=TokenUsage(),
        ))
        client = MagicMock(spec=AnthropicClient)

        plan = '{"steps": [{"action": "validate_product"}]}'
        await ex.execute(
            client=client,
            tool_handler=tool_handler,
            operativo_id="op-1",
            plan_json=plan,
            domain_memory="",
        )

        call_kwargs = tool_handler.run_loop.call_args
        prompt = call_kwargs.kwargs["prompt"]
        # The plan should appear in the user message
        user_messages = [m for m in prompt["messages"] if m["role"] == "user"]
        assert any("validate_product" in str(m["content"]) for m in user_messages)
