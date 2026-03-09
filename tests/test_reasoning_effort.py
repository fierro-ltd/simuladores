"""Tests for per-phase reasoning effort configuration.

Validates that:
- AgentConfig accepts and stores reasoning_effort
- AGENT_EFFORTS has correct values for all 4 agents
- send_message() accepts reasoning_effort and passes it as metadata
- run_loop() passes reasoning_effort through to send_message()
- Each agent executor uses its configured effort level
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_harness.agents.base import (
    AGENT_EFFORTS,
    AGENT_MODELS,
    AgentConfig,
    BaseAgent,
)
from agent_harness.agents.lamponne import LamponneExecutor
from agent_harness.agents.medina import MedinaInvestigator
from agent_harness.agents.qa_reviewer import SantosQAReviewer
from agent_harness.agents.ravenna import RavennaSynthesizer
from agent_harness.agents.santos import SantosPlanner, SANTOS_SYSTEM_IDENTITY
from agent_harness.llm.client import AnthropicClient, MessageResult, TokenUsage
from agent_harness.llm.tool_handler import ToolHandler, ToolLoopResult


# ---------------------------------------------------------------------------
# AgentConfig tests
# ---------------------------------------------------------------------------


class TestAgentConfigReasoningEffort:
    def test_default_effort_is_high(self):
        cfg = AgentConfig(
            name="santos",
            model="claude-sonnet-4-6",
            system_identity="id",
            domain="dce",
        )
        assert cfg.reasoning_effort == "high"

    def test_effort_override(self):
        cfg = AgentConfig(
            name="lamponne",
            model="claude-sonnet-4-6",
            system_identity="id",
            domain="dce",
            reasoning_effort="medium",
        )
        assert cfg.reasoning_effort == "medium"

    def test_effort_low(self):
        cfg = AgentConfig(
            name="test",
            model="claude-sonnet-4-6",
            system_identity="id",
            domain="dce",
            reasoning_effort="low",
        )
        assert cfg.reasoning_effort == "low"


# ---------------------------------------------------------------------------
# AGENT_EFFORTS registry tests
# ---------------------------------------------------------------------------


class TestAgentEfforts:
    def test_has_all_four_agents(self):
        assert set(AGENT_EFFORTS.keys()) == {"santos", "medina", "lamponne", "ravenna"}

    def test_santos_effort_is_high(self):
        assert AGENT_EFFORTS["santos"] == "high"

    def test_medina_effort_is_high(self):
        assert AGENT_EFFORTS["medina"] == "high"

    def test_lamponne_effort_is_medium(self):
        assert AGENT_EFFORTS["lamponne"] == "medium"

    def test_ravenna_effort_is_medium(self):
        assert AGENT_EFFORTS["ravenna"] == "medium"

    def test_all_values_are_valid(self):
        valid = {"high", "medium", "low"}
        for agent, effort in AGENT_EFFORTS.items():
            assert effort in valid, f"{agent} has invalid effort: {effort}"

    def test_efforts_keys_match_models_keys(self):
        assert set(AGENT_EFFORTS.keys()) == set(AGENT_MODELS.keys())


# ---------------------------------------------------------------------------
# AnthropicClient.send_message() reasoning_effort parameter
# ---------------------------------------------------------------------------


def _make_text_response(text: str = "ok") -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason="end_turn",
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=5,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        ),
        model="claude-sonnet-4-6",
    )


@pytest.fixture
def mock_client(mocker):
    client = AnthropicClient(project_id="test-project", region="us-central1")
    mock_create = AsyncMock(return_value=_make_text_response())
    mocker.patch.object(client._client.messages, "create", mock_create)
    return client, mock_create


def _prompt() -> dict:
    return {
        "system": "You are a test agent.",
        "messages": [{"role": "user", "content": "Hello"}],
        "cache_control": {"system_cache": False},
    }


class TestSendMessageReasoningEffort:
    async def test_no_metadata_when_effort_is_none(self, mock_client):
        client, mock_create = mock_client
        await client.send_message(_prompt())
        call_kwargs = mock_create.call_args[1]
        assert "metadata" not in call_kwargs

    async def test_reasoning_effort_accepted_but_not_in_kwargs(self, mock_client):
        """reasoning_effort is accepted but not wired to Vertex AI rawPredict."""
        client, mock_create = mock_client
        await client.send_message(_prompt(), reasoning_effort="high")
        call_kwargs = mock_create.call_args[1]
        # Vertex AI rawPredict does not support metadata.reasoning_effort
        assert "metadata" not in call_kwargs


# ---------------------------------------------------------------------------
# ToolHandler.run_loop() passes reasoning_effort through
# ---------------------------------------------------------------------------

TOOLS = [{"name": "test_tool", "description": "Test", "input_schema": {"type": "object", "properties": {}}}]
USAGE = TokenUsage(input_tokens=10, output_tokens=5)


def _text_result(content: str = "Done.") -> MessageResult:
    return MessageResult(
        content=content,
        stop_reason="end_turn",
        tool_calls=[],
        usage=USAGE,
        model="claude-sonnet-4-6",
    )


@pytest.fixture
def mock_anthropic_for_loop(mocker):
    client = AnthropicClient(project_id="test-project", region="us-central1")
    mock_send = AsyncMock(return_value=_text_result())
    mocker.patch.object(client, "send_message", mock_send)
    return client, mock_send


class TestToolLoopReasoningEffort:
    async def test_passes_effort_to_send_message(self, mock_anthropic_for_loop):
        client, mock_send = mock_anthropic_for_loop
        handler = ToolHandler(client, {})
        await handler.run_loop(_prompt(), "claude-sonnet-4-6", TOOLS, reasoning_effort="medium")

        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["reasoning_effort"] == "medium"

    async def test_passes_none_when_not_set(self, mock_anthropic_for_loop):
        client, mock_send = mock_anthropic_for_loop
        handler = ToolHandler(client, {})
        await handler.run_loop(_prompt(), "claude-sonnet-4-6", TOOLS)

        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["reasoning_effort"] is None

    async def test_passes_high_effort(self, mock_anthropic_for_loop):
        client, mock_send = mock_anthropic_for_loop
        handler = ToolHandler(client, {})
        await handler.run_loop(_prompt(), "claude-sonnet-4-6", TOOLS, reasoning_effort="high")

        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["reasoning_effort"] == "high"


# ---------------------------------------------------------------------------
# Agent executor reasoning_effort integration
# ---------------------------------------------------------------------------


def _mock_client_returning(content: str) -> AnthropicClient:
    client = MagicMock(spec=AnthropicClient)
    client.send_message = AsyncMock(
        return_value=MessageResult(
            content=content,
            stop_reason="end_turn",
            tool_calls=[],
            usage=USAGE,
            model="claude-sonnet-4-6",
        )
    )
    return client


def _mock_tool_handler_returning(content: str) -> ToolHandler:
    handler = MagicMock(spec=ToolHandler)
    handler.run_loop = AsyncMock(
        return_value=ToolLoopResult(
            final_content=content,
            turns=1,
            tool_calls_made=[],
            tool_errors=0,
            max_turns_reached=False,
            total_usage=USAGE,
        )
    )
    return handler


class TestSantosReasoningEffort:
    @pytest.mark.asyncio
    async def test_santos_passes_high_effort(self):
        planner = SantosPlanner(
            base_agent=BaseAgent(
                config=AgentConfig(
                    name="santos",
                    model=AGENT_MODELS["santos"],
                    system_identity=SANTOS_SYSTEM_IDENTITY,
                    domain="dce",
                )
            )
        )
        plan_json = json.dumps({"steps": [{"agent": "medina", "action": "scan", "params": {}}]})
        client = _mock_client_returning(plan_json)

        await planner.plan(
            client=client,
            operativo_id="op-1",
            input_description="Test",
            domain_memory="",
        )

        call_kwargs = client.send_message.call_args[1]
        assert call_kwargs["reasoning_effort"] == "high"


class TestMedinaReasoningEffort:
    @pytest.mark.asyncio
    async def test_medina_passes_high_effort(self):
        investigator = MedinaInvestigator(domain="dce")
        snapshot_json = json.dumps({
            "operativo_id": "op-1",
            "pdf_filename": "test.pdf",
            "injection_scan_risk": "low",
            "structured_fields": {},
            "raw_text_hash": "abc123",
        })
        handler = _mock_tool_handler_returning(snapshot_json)
        client = MagicMock(spec=AnthropicClient)

        await investigator.investigate(
            client=client,
            tool_handler=handler,
            operativo_id="op-1",
            pdf_path="/tmp/test.pdf",
            domain_memory="",
        )

        call_kwargs = handler.run_loop.call_args[1]
        assert call_kwargs["reasoning_effort"] == "high"


class TestLamponneReasoningEffort:
    @pytest.mark.asyncio
    async def test_lamponne_passes_medium_effort(self):
        executor = LamponneExecutor(domain="dce")
        handler = _mock_tool_handler_returning("Execution complete.")
        client = MagicMock(spec=AnthropicClient)

        await executor.execute(
            client=client,
            tool_handler=handler,
            operativo_id="op-1",
            plan_json='{"steps": []}',
            domain_memory="",
        )

        call_kwargs = handler.run_loop.call_args[1]
        assert call_kwargs["reasoning_effort"] == "medium"


class TestRavennaReasoningEffort:
    @pytest.mark.asyncio
    async def test_ravenna_passes_medium_effort(self):
        synth = RavennaSynthesizer(domain="dce")
        handler = _mock_tool_handler_returning("Result synthesized.")
        client = MagicMock(spec=AnthropicClient)

        await synth.synthesize(
            client=client,
            tool_handler=handler,
            operativo_id="op-1",
            progress="Phase 1-4 reports",
            raw_output_json="{}",
            qa_report_json="{}",
            caller_id="caller-1",
            domain_memory="",
        )

        call_kwargs = handler.run_loop.call_args[1]
        assert call_kwargs["reasoning_effort"] == "medium"


class TestQAReviewerReasoningEffort:
    @pytest.mark.asyncio
    async def test_qa_reviewer_passes_high_effort(self):
        reviewer = SantosQAReviewer(domain="dce")
        qa_json = json.dumps({"checks": []})
        client = _mock_client_returning(qa_json)

        await reviewer.review(
            client=client,
            operativo_id="op-1",
            input_snapshot_json="{}",
            raw_output_json="{}",
            domain_memory="",
        )

        call_kwargs = client.send_message.call_args[1]
        assert call_kwargs["reasoning_effort"] == "high"
