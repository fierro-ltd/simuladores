"""Tests for RavennaSynthesizer executor."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from agent_harness.agents.ravenna import (
    RAVENNA_SYSTEM_IDENTITY,
    RAVENNA_TOOLS,
    RavennaSynthesizer,
)
from agent_harness.agents.base import AGENT_MODELS
from agent_harness.llm.client import AnthropicClient, TokenUsage
from agent_harness.llm.tool_handler import ToolHandler, ToolLoopResult


class TestRavennaSynthesizerInit:
    def test_uses_sonnet_model(self):
        syn = RavennaSynthesizer(domain="dce")
        assert syn.config.model == AGENT_MODELS["ravenna"]
        assert syn.config.model == "claude-sonnet-4-6"

    def test_uses_ravenna_identity(self):
        syn = RavennaSynthesizer(domain="dce")
        assert syn.config.system_identity == RAVENNA_SYSTEM_IDENTITY

    def test_stores_domain(self):
        syn = RavennaSynthesizer(domain="dce")
        assert syn.config.domain == "dce"

    def test_agent_name_is_ravenna(self):
        syn = RavennaSynthesizer(domain="dce")
        assert syn.config.name == "ravenna"


class TestRavennaSynthesize:
    @pytest.mark.asyncio
    async def test_returns_final_content(self):
        syn = RavennaSynthesizer(domain="dce")

        tool_handler = MagicMock(spec=ToolHandler)
        tool_handler.run_loop = AsyncMock(return_value=ToolLoopResult(
            final_content='{"status": "completed", "operativo_id": "op-789"}',
            turns=4,
            tool_calls_made=[],
            tool_errors=0,
            max_turns_reached=False,
            total_usage=TokenUsage(),
        ))
        client = MagicMock(spec=AnthropicClient)

        result = await syn.synthesize(
            client=client,
            tool_handler=tool_handler,
            operativo_id="op-789",
            progress="Phase 1: Plan created.\nPhase 2: Investigation complete.",
            raw_output_json='{"extractions": []}',
            qa_report_json='{"total_checks": 5, "blocking": 0}',
            caller_id="user@example.com",
            domain_memory="# DCE Domain",
        )

        assert "op-789" in result

    @pytest.mark.asyncio
    async def test_calls_tool_handler_with_ravenna_tools(self):
        syn = RavennaSynthesizer(domain="dce")

        tool_handler = MagicMock(spec=ToolHandler)
        tool_handler.run_loop = AsyncMock(return_value=ToolLoopResult(
            final_content="done",
            turns=1,
            total_usage=TokenUsage(),
        ))
        client = MagicMock(spec=AnthropicClient)

        await syn.synthesize(
            client=client,
            tool_handler=tool_handler,
            operativo_id="op-1",
            progress="",
            raw_output_json="{}",
            qa_report_json="{}",
            caller_id="test",
            domain_memory="",
        )

        tool_handler.run_loop.assert_called_once()
        call_kwargs = tool_handler.run_loop.call_args
        assert call_kwargs.kwargs["tools"] == RAVENNA_TOOLS
        assert call_kwargs.kwargs["model"] == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_prompt_contains_operativo_id(self):
        syn = RavennaSynthesizer(domain="dce")

        tool_handler = MagicMock(spec=ToolHandler)
        tool_handler.run_loop = AsyncMock(return_value=ToolLoopResult(
            final_content="done",
            turns=1,
            total_usage=TokenUsage(),
        ))
        client = MagicMock(spec=AnthropicClient)

        await syn.synthesize(
            client=client,
            tool_handler=tool_handler,
            operativo_id="op-synth-42",
            progress="Phase 1 done",
            raw_output_json="{}",
            qa_report_json="{}",
            caller_id="admin",
            domain_memory="# DCE",
        )

        call_kwargs = tool_handler.run_loop.call_args
        prompt = call_kwargs.kwargs["prompt"]
        user_messages = [m for m in prompt["messages"] if m["role"] == "user"]
        assert any("op-synth-42" in str(m["content"]) for m in user_messages)

    @pytest.mark.asyncio
    async def test_prompt_includes_caller_id(self):
        syn = RavennaSynthesizer(domain="dce")

        tool_handler = MagicMock(spec=ToolHandler)
        tool_handler.run_loop = AsyncMock(return_value=ToolLoopResult(
            final_content="done",
            turns=1,
            total_usage=TokenUsage(),
        ))
        client = MagicMock(spec=AnthropicClient)

        await syn.synthesize(
            client=client,
            tool_handler=tool_handler,
            operativo_id="op-1",
            progress="",
            raw_output_json="{}",
            qa_report_json="{}",
            caller_id="special-caller@example.com",
            domain_memory="",
        )

        call_kwargs = tool_handler.run_loop.call_args
        prompt = call_kwargs.kwargs["prompt"]
        user_messages = [m for m in prompt["messages"] if m["role"] == "user"]
        assert any("special-caller@example.com" in str(m["content"]) for m in user_messages)

    @pytest.mark.asyncio
    async def test_prompt_includes_qa_report(self):
        syn = RavennaSynthesizer(domain="dce")

        tool_handler = MagicMock(spec=ToolHandler)
        tool_handler.run_loop = AsyncMock(return_value=ToolLoopResult(
            final_content="done",
            turns=1,
            total_usage=TokenUsage(),
        ))
        client = MagicMock(spec=AnthropicClient)

        await syn.synthesize(
            client=client,
            tool_handler=tool_handler,
            operativo_id="op-1",
            progress="",
            raw_output_json="{}",
            qa_report_json='{"blocking": 2, "warnings": 1}',
            caller_id="test",
            domain_memory="",
        )

        call_kwargs = tool_handler.run_loop.call_args
        prompt = call_kwargs.kwargs["prompt"]
        user_messages = [m for m in prompt["messages"] if m["role"] == "user"]
        assert any("blocking" in str(m["content"]) for m in user_messages)
