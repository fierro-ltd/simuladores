"""Tests for activities/implementations.py — all 6 activity functions."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_harness.activities.agent_loop import AgentLoopInput, AgentLoopOutput
from agent_harness.activities.implementations import (
    cpc_web_verify,
    lamponne_execute,
    medina_investigate,
    post_job_learn,
    ravenna_synthesize,
    santos_plan,
    santos_qa_review,
)
from agent_harness.activities.investigator import (
    InputSnapshot,
    InvestigatorInput,
    InvestigatorOutput,
)
from agent_harness.activities.planner import PlannerInput, PlannerOutput
from agent_harness.activities.post_job import PostJobInput, PostJobOutput
from agent_harness.activities.qa_review import QAReviewInput, QAReviewOutput
from agent_harness.activities.synthesizer import SynthesizerInput, SynthesizerOutput
from agent_harness.activities.web_verify import WebVerifyInput, WebVerifyOutput
from agent_harness.core.operativo import Severity
from agent_harness.core.plan import AgentTask, ExecutionPlan
from agent_harness.agents.qa_reviewer import QACheck, QAReport


# Common patch paths
_PATCH_PREFIX = "agent_harness.activities.implementations"
_FACTORY_PREFIX = "agent_harness.activities.factory"


def _mock_client():
    """Create a mock AnthropicClient."""
    return MagicMock()


def _mock_tool_handler():
    """Create a mock ToolHandler."""
    return MagicMock()


def _mock_storage_backend(domain_content: str = "# DCE Domain"):
    """Create a mock LocalStorageBackend that returns domain content."""
    backend = MagicMock()
    backend.read = AsyncMock(return_value=domain_content.encode("utf-8"))
    return backend


class TestSantosPlan:
    """Tests for santos_plan activity."""

    @pytest.mark.asyncio
    async def test_santos_plan_returns_planner_output(self) -> None:
        mock_plan = ExecutionPlan(
            operativo_id="op-001",
            tasks=[
                AgentTask(agent="medina", action="investigate", params={"pdf": "test.pdf"}),
                AgentTask(agent="lamponne", action="execute", params={}),
            ],
        )

        with (
            patch(f"{_PATCH_PREFIX}.get_anthropic_client", return_value=_mock_client()),
            patch(f"{_PATCH_PREFIX}._get_storage_backend", return_value=_mock_storage_backend()),
            patch(f"{_PATCH_PREFIX}.load_domain_memory", new_callable=AsyncMock, return_value="# DCE"),
            patch("agent_harness.agents.santos.SantosPlanner.plan", new_callable=AsyncMock, return_value=mock_plan),
        ):
            input_data = PlannerInput(
                operativo_id="op-001",
                domain="dce",
                pdf_description="Test DCE document",
            )
            result = await santos_plan(input_data)

        assert isinstance(result, PlannerOutput)
        assert result.operativo_id == "op-001"
        plan_data = json.loads(result.plan_json)
        assert len(plan_data["steps"]) == 2
        assert plan_data["steps"][0]["agent"] == "medina"
        assert "santos" in result.phase_result.lower() or "planned" in result.phase_result.lower()


class TestMedinaInvestigate:
    """Tests for medina_investigate activity."""

    @pytest.mark.asyncio
    async def test_medina_investigate_returns_output(self) -> None:
        mock_snapshot = InputSnapshot(
            operativo_id="op-002",
            pdf_filename="test.pdf",
            injection_scan_risk="none",
            structured_fields={"product_name": "Widget"},
            raw_text_hash="abc123",
        )

        with (
            patch(f"{_PATCH_PREFIX}.get_anthropic_client", return_value=_mock_client()),
            patch(f"{_PATCH_PREFIX}._get_storage_backend", return_value=_mock_storage_backend()),
            patch(f"{_PATCH_PREFIX}.load_domain_memory", new_callable=AsyncMock, return_value="# DCE"),
            patch(f"{_PATCH_PREFIX}.build_tool_handler", return_value=_mock_tool_handler()),
            patch(
                "agent_harness.agents.medina.MedinaInvestigator.investigate",
                new_callable=AsyncMock,
                return_value=mock_snapshot,
            ),
        ):
            input_data = InvestigatorInput(
                operativo_id="op-002",
                domain="dce",
                pdf_path="/docs/test.pdf",
                pdf_filename="test.pdf",
            )
            result = await medina_investigate(input_data)

        assert isinstance(result, InvestigatorOutput)
        assert result.operativo_id == "op-002"
        assert result.injection_risk == "none"
        assert result.halted is False
        snapshot_data = json.loads(result.input_snapshot_json)
        assert snapshot_data["structured_fields"]["product_name"] == "Widget"

    @pytest.mark.asyncio
    async def test_medina_investigate_halts_on_high_risk(self) -> None:
        mock_snapshot = InputSnapshot(
            operativo_id="op-003",
            pdf_filename="malicious.pdf",
            injection_scan_risk="high",
            structured_fields={},
            raw_text_hash="xyz789",
        )

        with (
            patch(f"{_PATCH_PREFIX}.get_anthropic_client", return_value=_mock_client()),
            patch(f"{_PATCH_PREFIX}._get_storage_backend", return_value=_mock_storage_backend()),
            patch(f"{_PATCH_PREFIX}.load_domain_memory", new_callable=AsyncMock, return_value="# DCE"),
            patch(f"{_PATCH_PREFIX}.build_tool_handler", return_value=_mock_tool_handler()),
            patch(
                "agent_harness.agents.medina.MedinaInvestigator.investigate",
                new_callable=AsyncMock,
                return_value=mock_snapshot,
            ),
        ):
            input_data = InvestigatorInput(
                operativo_id="op-003",
                domain="dce",
                pdf_path="/docs/malicious.pdf",
                pdf_filename="malicious.pdf",
            )
            result = await medina_investigate(input_data)

        assert result.injection_risk == "high"
        assert result.halted is True


class TestLamponneExecute:
    """Tests for lamponne_execute activity."""

    @pytest.mark.asyncio
    async def test_lamponne_execute_returns_output(self) -> None:
        with (
            patch(f"{_PATCH_PREFIX}.get_anthropic_client", return_value=_mock_client()),
            patch(f"{_PATCH_PREFIX}._get_storage_backend", return_value=_mock_storage_backend()),
            patch(f"{_PATCH_PREFIX}.load_domain_memory", new_callable=AsyncMock, return_value="# DCE"),
            patch(f"{_PATCH_PREFIX}.build_tool_handler", return_value=_mock_tool_handler()),
            patch(
                "agent_harness.agents.lamponne.LamponneExecutor.execute",
                new_callable=AsyncMock,
                return_value="Execution completed successfully.",
            ),
        ):
            input_data = AgentLoopInput(
                agent_name="lamponne",
                domain="dce",
                operativo_id="op-004",
                task_message='{"steps": []}',
                available_tools=["discover_api", "execute_api"],
                max_turns=5,
            )
            result = await lamponne_execute(input_data)

        assert isinstance(result, AgentLoopOutput)
        assert result.final_response == "Execution completed successfully."


class TestSantosQAReview:
    """Tests for santos_qa_review activity."""

    @pytest.mark.asyncio
    async def test_santos_qa_review_completed(self) -> None:
        mock_report = QAReport(
            operativo_id="op-005",
            checks=[
                QACheck(
                    field="product_name",
                    expected="Widget A",
                    actual="Widget A",
                    severity=Severity.INFO,
                    auto_correctable=False,
                ),
            ],
        )

        with (
            patch(f"{_PATCH_PREFIX}.get_anthropic_client", return_value=_mock_client()),
            patch(f"{_PATCH_PREFIX}._get_storage_backend", return_value=_mock_storage_backend()),
            patch(f"{_PATCH_PREFIX}.load_domain_memory", new_callable=AsyncMock, return_value="# DCE"),
            patch(
                "agent_harness.agents.qa_reviewer.SantosQAReviewer.review",
                new_callable=AsyncMock,
                return_value=mock_report,
            ),
        ):
            input_data = QAReviewInput(
                operativo_id="op-005",
                domain="dce",
                input_snapshot_json='{"fields": {}}',
                raw_output_json='{"result": {}}',
            )
            result = await santos_qa_review(input_data)

        assert isinstance(result, QAReviewOutput)
        assert result.operativo_id == "op-005"
        assert result.final_status == "COMPLETED"
        qa_data = json.loads(result.qa_report_json)
        assert len(qa_data["checks"]) == 1

    @pytest.mark.asyncio
    async def test_santos_qa_review_needs_review(self) -> None:
        mock_report = QAReport(
            operativo_id="op-006",
            checks=[
                QACheck(
                    field="manufacturer",
                    expected="Acme Inc",
                    actual="ACME Corp",
                    severity=Severity.BLOCKING,
                    auto_correctable=True,
                ),
            ],
        )

        with (
            patch(f"{_PATCH_PREFIX}.get_anthropic_client", return_value=_mock_client()),
            patch(f"{_PATCH_PREFIX}._get_storage_backend", return_value=_mock_storage_backend()),
            patch(f"{_PATCH_PREFIX}.load_domain_memory", new_callable=AsyncMock, return_value="# DCE"),
            patch(
                "agent_harness.agents.qa_reviewer.SantosQAReviewer.review",
                new_callable=AsyncMock,
                return_value=mock_report,
            ),
        ):
            input_data = QAReviewInput(
                operativo_id="op-006",
                domain="dce",
                input_snapshot_json='{"fields": {}}',
                raw_output_json='{"result": {}}',
            )
            result = await santos_qa_review(input_data)

        assert result.final_status == "NEEDS_REVIEW"


class TestRavennaSynthesize:
    """Tests for ravenna_synthesize activity."""

    @pytest.mark.asyncio
    async def test_ravenna_synthesize_returns_output(self) -> None:
        with (
            patch(f"{_PATCH_PREFIX}.get_anthropic_client", return_value=_mock_client()),
            patch(f"{_PATCH_PREFIX}._get_storage_backend", return_value=_mock_storage_backend()),
            patch(f"{_PATCH_PREFIX}.load_domain_memory", new_callable=AsyncMock, return_value="# DCE"),
            patch(f"{_PATCH_PREFIX}.build_tool_handler", return_value=_mock_tool_handler()),
            patch(
                "agent_harness.agents.ravenna.RavennaSynthesizer.synthesize",
                new_callable=AsyncMock,
                return_value='{"status": "COMPLETED", "result": {}}',
            ),
        ):
            input_data = SynthesizerInput(
                operativo_id="op-007",
                domain="dce",
                progress_entries="Phase 1: Santos planned...",
                raw_output_json='{"execution": "done"}',
                qa_report_json='{"checks": []}',
                caller_id="user-001",
            )
            result = await ravenna_synthesize(input_data)

        assert isinstance(result, SynthesizerOutput)
        assert result.operativo_id == "op-007"
        assert result.delivery_permitted is True
        assert "/reports/op-007/" in result.report_url

    @pytest.mark.asyncio
    async def test_ravenna_adds_web_verification_when_citation_report_ambiguous(self) -> None:
        """When citation_completeness_report has web_verification_recommended, structured_result includes it."""
        citation_report = '{"provided_citations": ["SOR-2018-83"], "web_verification_recommended": true}'
        with (
            patch(f"{_PATCH_PREFIX}.get_anthropic_client", return_value=_mock_client()),
            patch(f"{_PATCH_PREFIX}._get_storage_backend", return_value=_mock_storage_backend()),
            patch(f"{_PATCH_PREFIX}.load_domain_memory", new_callable=AsyncMock, return_value="# DCE"),
            patch(f"{_PATCH_PREFIX}.build_tool_handler", return_value=_mock_tool_handler()),
            patch(
                "agent_harness.agents.ravenna.RavennaSynthesizer.synthesize",
                new_callable=AsyncMock,
                return_value='{"status": "COMPLETED", "result": {}}',
            ),
        ):
            input_data = SynthesizerInput(
                operativo_id="op-007",
                domain="dce",
                progress_entries="Phase 1: Santos planned...",
                raw_output_json='{"execution": "done"}',
                qa_report_json='{"checks": []}',
                caller_id="user-001",
                citation_completeness_report_json=citation_report,
            )
            result = await ravenna_synthesize(input_data)

        parsed = __import__("json").loads(result.structured_result_json)
        assert parsed.get("web_verification_recommended") is True


class TestCpcWebVerify:
    """Tests for cpc_web_verify activity."""

    @pytest.mark.asyncio
    async def test_web_verify_skips_when_no_queries(self) -> None:
        input_data = WebVerifyInput(
            operativo_id="op-wv-1",
            domain="dce",
            citation_completeness_report_json='{"missing_citations":[],"invalid_citations":[]}',
        )
        result = await cpc_web_verify(input_data)
        assert isinstance(result, WebVerifyOutput)
        payload = json.loads(result.verification_json)
        assert payload["queries"] == []
        assert payload["results"] == []


class TestPostJobLearn:
    """Tests for post_job_learn activity."""

    @pytest.mark.asyncio
    async def test_post_job_learn_returns_output(self) -> None:
        input_data = PostJobInput(
            operativo_id="op-008",
            domain="dce",
            session_progress="All phases completed.",
        )
        result = await post_job_learn(input_data)

        assert isinstance(result, PostJobOutput)
        assert result.operativo_id == "op-008"
        assert result.patterns_extracted == 0
        assert result.archived is True

    @pytest.mark.asyncio
    async def test_post_job_learn_no_llm_call(self) -> None:
        """post_job_learn should NOT call get_anthropic_client."""
        with patch(f"{_PATCH_PREFIX}.get_anthropic_client") as mock_client:
            input_data = PostJobInput(
                operativo_id="op-009",
                domain="dce",
                session_progress="Done.",
            )
            await post_job_learn(input_data)
            mock_client.assert_not_called()
