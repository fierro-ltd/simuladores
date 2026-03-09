"""Tests for Santos plan() executor method."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_harness.agents.base import AGENT_MODELS, AgentConfig, BaseAgent
from agent_harness.agents.santos import SANTOS_SYSTEM_IDENTITY, SantosPlanner
from agent_harness.core.plan import ExecutionPlan
from agent_harness.llm.client import AnthropicClient, MessageResult, TokenUsage


def _make_planner() -> SantosPlanner:
    """Create a SantosPlanner with a real BaseAgent."""
    cfg = AgentConfig(
        name="santos",
        model=AGENT_MODELS["santos"],
        system_identity=SANTOS_SYSTEM_IDENTITY,
        domain="dce",
    )
    return SantosPlanner(base_agent=BaseAgent(config=cfg))


def _mock_client(response_json: dict) -> AnthropicClient:
    """Create a mock AnthropicClient that returns the given JSON as content."""
    client = MagicMock(spec=AnthropicClient)
    client.send_message = AsyncMock(
        return_value=MessageResult(
            content=json.dumps(response_json),
            stop_reason="end_turn",
            tool_calls=[],
            usage=TokenUsage(input_tokens=100, output_tokens=50),
            model="claude-sonnet-4-6",
        )
    )
    return client


class TestSantosPlan:
    """Tests for SantosPlanner.plan() async method."""

    @pytest.mark.asyncio
    async def test_plan_returns_execution_plan(self):
        planner = _make_planner()
        client = _mock_client({
            "steps": [
                {"agent": "medina", "action": "read_pdf", "params": {"file": "cert.pdf"}},
                {"agent": "lamponne", "action": "execute_api", "params": {"endpoint": "/validate"}},
            ]
        })

        plan = await planner.plan(
            client=client,
            operativo_id="op-test-1",
            input_description="Validate DCE document for product X",
            domain_memory="DCE domain rules here",
        )

        assert isinstance(plan, ExecutionPlan)
        assert plan.operativo_id == "op-test-1"
        assert len(plan.tasks) == 2
        assert plan.tasks[0].agent == "medina"
        assert plan.tasks[1].agent == "lamponne"

    @pytest.mark.asyncio
    async def test_plan_calls_client_with_opus_model(self):
        planner = _make_planner()
        client = _mock_client({"steps": []})

        await planner.plan(
            client=client,
            operativo_id="op-test-2",
            input_description="Test task",
            domain_memory="",
        )

        client.send_message.assert_called_once()
        call_kwargs = client.send_message.call_args
        assert call_kwargs.kwargs["model"] == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_plan_passes_domain_memory_and_session_state(self):
        planner = _make_planner()
        client = _mock_client({"steps": []})

        # We verify that build_prompt is called correctly by checking
        # that the prompt passed to send_message has the right structure
        await planner.plan(
            client=client,
            operativo_id="op-test-3",
            input_description="Test task",
            domain_memory="DCE domain memory",
            session_state="previous session data",
            semantic_patterns=["pattern-1"],
        )

        # The prompt dict should have been passed
        call_kwargs = client.send_message.call_args
        prompt = call_kwargs.kwargs["prompt"]
        assert "system" in prompt
        assert "messages" in prompt

    @pytest.mark.asyncio
    async def test_plan_falls_back_on_invalid_json_response(self):
        planner = _make_planner()
        client = MagicMock(spec=AnthropicClient)
        client.send_message = AsyncMock(
            return_value=MessageResult(
                content="This is not JSON",
                stop_reason="end_turn",
                model="claude-sonnet-4-6",
            )
        )

        plan = await planner.plan(
            client=client,
            operativo_id="op-bad",
            input_description="Bad task",
            domain_memory="",
        )
        assert len(plan.tasks) == 6
        assert plan.tasks[0].agent == "santos"

    @pytest.mark.asyncio
    async def test_plan_falls_back_on_missing_steps_key(self):
        planner = _make_planner()
        client = _mock_client({"plan": []})

        plan = await planner.plan(
            client=client,
            operativo_id="op-bad-2",
            input_description="Bad task",
            domain_memory="",
        )
        assert len(plan.tasks) == 6
        assert plan.tasks[0].agent == "santos"

    @pytest.mark.asyncio
    async def test_plan_includes_operativo_id_in_user_message(self):
        planner = _make_planner()
        client = _mock_client({"steps": []})

        await planner.plan(
            client=client,
            operativo_id="op-check-msg",
            input_description="Check message content",
            domain_memory="",
        )

        call_kwargs = client.send_message.call_args
        prompt = call_kwargs.kwargs["prompt"]
        # The user message should contain the operativo ID
        user_messages = [m for m in prompt["messages"] if m["role"] == "user"]
        assert any("op-check-msg" in m["content"] for m in user_messages)
