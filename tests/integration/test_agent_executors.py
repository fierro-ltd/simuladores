"""Integration test: all agents work with mocked SDK end-to-end."""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from agent_harness.agents import (
    SantosPlanner,
    SantosQAReviewer,
    MedinaInvestigator,
    LamponneExecutor,
    RavennaSynthesizer,
    BaseAgent,
    AgentConfig,
    AGENT_MODELS,
)
from agent_harness.llm import (
    AnthropicClient,
    ToolHandler,
    ToolLoopResult,
    MessageResult,
    TokenUsage,
)


def _usage():
    return TokenUsage(
        input_tokens=100, output_tokens=50,
        cache_creation_tokens=0, cache_read_tokens=0,
    )


@pytest.mark.asyncio
async def test_full_agent_chain():
    """All 5 agent operations execute in sequence (mocked)."""
    client = MagicMock(spec=AnthropicClient)

    # Phase 1: Santos plans
    client.send_message = AsyncMock(return_value=MessageResult(
        content=json.dumps({"steps": [
            {"agent": "medina", "action": "investigate", "params": {}},
            {"agent": "lamponne", "action": "execute", "params": {}},
        ]}),
        stop_reason="end_turn", tool_calls=[], usage=_usage(), model="claude-sonnet-4-6",
    ))
    config = AgentConfig(
        name="santos", model=AGENT_MODELS["santos"],
        system_identity="test", domain="dce",
    )
    plan = await SantosPlanner(BaseAgent(config)).plan(
        client=client, operativo_id="dce-int1",
        input_description="test.pdf", domain_memory="",
    )
    assert len(plan.tasks) == 2
    assert plan.tasks[0].agent == "medina"

    # Phase 2: Medina investigates
    tool_handler = MagicMock(spec=ToolHandler)
    tool_handler.run_loop = AsyncMock(return_value=ToolLoopResult(
        final_content=json.dumps({
            "operativo_id": "dce-int1", "pdf_filename": "test.pdf",
            "injection_scan_risk": "none",
            "structured_fields": {"name": "Widget"},
            "raw_text_hash": "hash1",
        }),
        turns=2, tool_calls_made=[], tool_errors=0,
        max_turns_reached=False, total_usage=_usage(),
    ))
    snapshot = await MedinaInvestigator(domain="dce").investigate(
        client=client, tool_handler=tool_handler, operativo_id="dce-int1",
        pdf_path="/tmp/test.pdf", domain_memory="",
    )
    assert snapshot.injection_scan_risk == "none"
    assert snapshot.structured_fields["name"] == "Widget"

    # Phase 3: Lamponne executes
    tool_handler.run_loop = AsyncMock(return_value=ToolLoopResult(
        final_content='{"result": "done"}',
        turns=3, tool_calls_made=[], tool_errors=0,
        max_turns_reached=False, total_usage=_usage(),
    ))
    output = await LamponneExecutor(domain="dce").execute(
        client=client, tool_handler=tool_handler, operativo_id="dce-int1",
        plan_json=json.dumps({"steps": []}), domain_memory="",
    )
    assert "done" in output

    # Phase 4: Santos QA
    client.send_message = AsyncMock(return_value=MessageResult(
        content=json.dumps({"checks": []}),
        stop_reason="end_turn", tool_calls=[], usage=_usage(), model="claude-sonnet-4-6",
    ))
    report = await SantosQAReviewer(domain="dce").review(
        client=client, operativo_id="dce-int1",
        input_snapshot_json=json.dumps(snapshot.structured_fields),
        raw_output_json=output, domain_memory="",
    )
    assert report.all_resolved

    # Phase 5: Ravenna synthesizes
    tool_handler.run_loop = AsyncMock(return_value=ToolLoopResult(
        final_content=json.dumps({"status": "COMPLETED", "operativo_id": "dce-int1"}),
        turns=2, tool_calls_made=[], tool_errors=0,
        max_turns_reached=False, total_usage=_usage(),
    ))
    result = await RavennaSynthesizer(domain="dce").synthesize(
        client=client, tool_handler=tool_handler, operativo_id="dce-int1",
        progress="progress", raw_output_json=output,
        qa_report_json=json.dumps({"checks": []}),
        caller_id="user-001", domain_memory="",
    )
    assert "COMPLETED" in result


@pytest.mark.asyncio
async def test_imports_from_agents_package():
    """Verify all executor classes are exported from agents package."""
    from agent_harness.agents import (
        LamponneExecutor,
        MedinaInvestigator,
        RavennaSynthesizer,
        SantosQAReviewer,
    )
    assert LamponneExecutor is not None
    assert MedinaInvestigator is not None
    assert RavennaSynthesizer is not None
    assert SantosQAReviewer is not None
