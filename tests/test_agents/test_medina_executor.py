"""Tests for MedinaInvestigator executor."""

from __future__ import annotations

import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from agent_harness.agents.medina import (
    MEDINA_SYSTEM_IDENTITY,
    MEDINA_TOOLS,
    MedinaInvestigator,
    _parse_snapshot,
)
from agent_harness.agents.base import AGENT_MODELS
from agent_harness.activities.investigator import InputSnapshot
from agent_harness.llm.client import AnthropicClient, TokenUsage
from agent_harness.llm.tool_handler import ToolHandler, ToolLoopResult


class TestMedinaInvestigatorInit:
    def test_uses_opus_model(self):
        inv = MedinaInvestigator(domain="dce")
        assert inv.config.model == AGENT_MODELS["medina"]
        assert inv.config.model == "claude-sonnet-4-6"

    def test_uses_medina_identity(self):
        inv = MedinaInvestigator(domain="dce")
        assert inv.config.system_identity == MEDINA_SYSTEM_IDENTITY

    def test_stores_domain(self):
        inv = MedinaInvestigator(domain="dce")
        assert inv.config.domain == "dce"

    def test_agent_name_is_medina(self):
        inv = MedinaInvestigator(domain="dce")
        assert inv.config.name == "medina"


class TestMedinaInvestigate:
    @pytest.mark.asyncio
    async def test_returns_input_snapshot(self):
        inv = MedinaInvestigator(domain="dce")

        snapshot_json = json.dumps({
            "operativo_id": "op-123",
            "pdf_filename": "test.pdf",
            "injection_scan_risk": "none",
            "structured_fields": {"product": "Widget", "country": "Nigeria"},
            "raw_text_hash": "abc123",
        })

        tool_handler = MagicMock(spec=ToolHandler)
        tool_handler.run_loop = AsyncMock(return_value=ToolLoopResult(
            final_content=snapshot_json,
            turns=3,
            tool_calls_made=[],
            tool_errors=0,
            max_turns_reached=False,
            total_usage=TokenUsage(),
        ))

        client = MagicMock(spec=AnthropicClient)

        result = await inv.investigate(
            client=client,
            tool_handler=tool_handler,
            operativo_id="op-123",
            pdf_path="/tmp/test.pdf",
            domain_memory="# DCE Domain",
        )

        assert isinstance(result, InputSnapshot)
        assert result.operativo_id == "op-123"
        assert result.pdf_filename == "test.pdf"
        assert result.injection_scan_risk == "none"
        assert result.structured_fields == {"product": "Widget", "country": "Nigeria"}
        assert result.raw_text_hash == "abc123"

    @pytest.mark.asyncio
    async def test_calls_tool_handler_with_medina_tools(self):
        inv = MedinaInvestigator(domain="dce")

        snapshot_json = json.dumps({
            "operativo_id": "op-123",
            "pdf_filename": "test.pdf",
            "injection_scan_risk": "none",
            "structured_fields": {},
            "raw_text_hash": "hash",
        })

        tool_handler = MagicMock(spec=ToolHandler)
        tool_handler.run_loop = AsyncMock(return_value=ToolLoopResult(
            final_content=snapshot_json,
            turns=1,
            total_usage=TokenUsage(),
        ))

        client = MagicMock(spec=AnthropicClient)

        await inv.investigate(
            client=client,
            tool_handler=tool_handler,
            operativo_id="op-123",
            pdf_path="/tmp/test.pdf",
            domain_memory="# DCE",
        )

        tool_handler.run_loop.assert_called_once()
        call_kwargs = tool_handler.run_loop.call_args
        assert call_kwargs.kwargs["tools"] == MEDINA_TOOLS
        assert call_kwargs.kwargs["model"] == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_passes_session_state(self):
        inv = MedinaInvestigator(domain="dce")

        snapshot_json = json.dumps({
            "operativo_id": "op-1",
            "pdf_filename": "f.pdf",
            "injection_scan_risk": "none",
            "structured_fields": {},
            "raw_text_hash": "",
        })

        tool_handler = MagicMock(spec=ToolHandler)
        tool_handler.run_loop = AsyncMock(return_value=ToolLoopResult(
            final_content=snapshot_json,
            turns=1,
            total_usage=TokenUsage(),
        ))
        client = MagicMock(spec=AnthropicClient)

        await inv.investigate(
            client=client,
            tool_handler=tool_handler,
            operativo_id="op-1",
            pdf_path="/tmp/f.pdf",
            domain_memory="# DCE",
            session_state="Phase 2 in progress",
        )

        # Verify the prompt was built (run_loop was called with a prompt dict)
        call_kwargs = tool_handler.run_loop.call_args
        prompt = call_kwargs.kwargs["prompt"]
        assert isinstance(prompt, dict)
        assert "system" in prompt
        assert "messages" in prompt

    @pytest.mark.asyncio
    async def test_raises_on_invalid_json_output(self):
        inv = MedinaInvestigator(domain="dce")

        tool_handler = MagicMock(spec=ToolHandler)
        tool_handler.run_loop = AsyncMock(return_value=ToolLoopResult(
            final_content="This is not JSON at all",
            turns=1,
            total_usage=TokenUsage(),
        ))
        client = MagicMock(spec=AnthropicClient)

        with pytest.raises(ValueError, match="Could not parse"):
            await inv.investigate(
                client=client,
                tool_handler=tool_handler,
                operativo_id="op-bad",
                pdf_path="/tmp/bad.pdf",
                domain_memory="",
            )


class TestParseSnapshot:
    def test_parses_valid_json(self):
        raw = json.dumps({
            "operativo_id": "op-1",
            "pdf_filename": "doc.pdf",
            "injection_scan_risk": "low",
            "structured_fields": {"key": "val"},
            "raw_text_hash": "h1",
        })
        snap = _parse_snapshot(raw, "op-1", "/tmp/doc.pdf")
        assert snap.operativo_id == "op-1"
        assert snap.injection_scan_risk == "low"

    def test_parses_json_in_code_fence(self):
        raw = '```json\n{"operativo_id": "op-2", "pdf_filename": "x.pdf", "injection_scan_risk": "none", "structured_fields": {}, "raw_text_hash": "h"}\n```'
        snap = _parse_snapshot(raw, "op-2", "/tmp/x.pdf")
        assert snap.operativo_id == "op-2"

    def test_uses_defaults_for_missing_fields(self):
        raw = json.dumps({"structured_fields": {"a": 1}})
        snap = _parse_snapshot(raw, "op-3", "/tmp/fallback.pdf")
        assert snap.operativo_id == "op-3"
        assert snap.pdf_filename == "fallback.pdf"
        assert snap.injection_scan_risk == "unknown"
        assert snap.raw_text_hash == ""

    def test_raises_on_garbage(self):
        with pytest.raises(ValueError):
            _parse_snapshot("not json", "op-x", "/tmp/x.pdf")
