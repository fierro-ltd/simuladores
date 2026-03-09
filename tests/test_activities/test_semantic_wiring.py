"""Tests for semantic pattern injection into DCE activities.

Verifies that each activity retrieves patterns from MemoryRecall and
BulletinStore and passes them through to the agent's build_prompt.
"""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_harness.activities.implementations import (
    lamponne_execute,
    medina_investigate,
    ravenna_synthesize,
    santos_plan,
    santos_qa_review,
)
from agent_harness.activities.agent_loop import AgentLoopInput
from agent_harness.activities.investigator import (
    InputSnapshot,
    InvestigatorInput,
)
from agent_harness.activities.planner import PlannerInput
from agent_harness.activities.qa_review import QAReviewInput
from agent_harness.activities.synthesizer import SynthesizerInput
from agent_harness.agents.qa_reviewer import QACheck, QAReport
from agent_harness.core.operativo import Severity
from agent_harness.core.plan import AgentTask, ExecutionPlan

_IMPL = "agent_harness.activities.implementations"


def _standard_patches():
    """Return common patches used by all activity tests."""
    return [
        patch(f"{_IMPL}.get_anthropic_client", return_value=MagicMock()),
        patch(f"{_IMPL}._get_storage_backend", return_value=MagicMock()),
        patch(f"{_IMPL}.load_domain_memory", new_callable=AsyncMock, return_value="# DCE"),
        patch(f"{_IMPL}.build_tool_handler", return_value=MagicMock()),
    ]


@contextlib.contextmanager
def _all_patches(*extra_patches):
    """Apply standard patches plus any extra patches."""
    with contextlib.ExitStack() as stack:
        mocks = {}
        for p in _standard_patches():
            stack.enter_context(p)
        for p in extra_patches:
            m = stack.enter_context(p)
            mocks[p.attribute] = m
        yield mocks


class TestSantosPlanReceivesPatterns:
    """Verify santos_plan retrieves and passes semantic patterns."""

    @pytest.mark.asyncio
    async def test_santos_plan_calls_retrieve_patterns(self) -> None:
        mock_plan = ExecutionPlan(
            operativo_id="op-sp-1",
            tasks=[AgentTask(agent="medina", action="investigate", params={})],
        )

        retrieve_patch = patch(
            f"{_IMPL}._retrieve_semantic_patterns",
            new_callable=AsyncMock,
            return_value=["[pattern] test pattern"],
        )
        plan_patch = patch(
            "agent_harness.agents.santos.SantosPlanner.plan",
            new_callable=AsyncMock,
            return_value=mock_plan,
        )

        with _all_patches(retrieve_patch, plan_patch) as mocks:
            mock_retrieve = mocks["_retrieve_semantic_patterns"]
            mock_plan_call = mocks["plan"]

            input_data = PlannerInput(
                operativo_id="op-sp-1",
                domain="dce",
                pdf_description="Test DCE document",
            )
            await santos_plan(input_data)

            mock_retrieve.assert_called_once()
            assert mock_retrieve.call_args[0][0] == "dce"

            call_kwargs = mock_plan_call.call_args[1]
            assert call_kwargs["semantic_patterns"] == ["[pattern] test pattern"]


class TestMedinaInvestigateReceivesPatterns:
    """Verify medina_investigate retrieves and passes semantic patterns."""

    @pytest.mark.asyncio
    async def test_medina_investigate_calls_retrieve_patterns(self) -> None:
        mock_snapshot = InputSnapshot(
            operativo_id="op-mi-1",
            pdf_filename="test.pdf",
            injection_scan_risk="none",
            structured_fields={},
            raw_text_hash="abc",
        )

        retrieve_patch = patch(
            f"{_IMPL}._retrieve_semantic_patterns",
            new_callable=AsyncMock,
            return_value=["[fact] DCE requires SONCAP"],
        )
        investigate_patch = patch(
            "agent_harness.agents.medina.MedinaInvestigator.investigate",
            new_callable=AsyncMock,
            return_value=mock_snapshot,
        )

        with _all_patches(retrieve_patch, investigate_patch) as mocks:
            mock_retrieve = mocks["_retrieve_semantic_patterns"]
            mock_investigate = mocks["investigate"]

            input_data = InvestigatorInput(
                operativo_id="op-mi-1",
                domain="dce",
                pdf_path="/docs/test.pdf",
                pdf_filename="test.pdf",
            )
            await medina_investigate(input_data)

            mock_retrieve.assert_called_once()
            call_kwargs = mock_investigate.call_args[1]
            assert call_kwargs["semantic_patterns"] == ["[fact] DCE requires SONCAP"]


class TestLamponneExecuteReceivesPatterns:
    """Verify lamponne_execute retrieves and passes semantic patterns."""

    @pytest.mark.asyncio
    async def test_lamponne_execute_calls_retrieve_patterns(self) -> None:
        retrieve_patch = patch(
            f"{_IMPL}._retrieve_semantic_patterns",
            new_callable=AsyncMock,
            return_value=["[pattern] extraction order matters"],
        )
        execute_patch = patch(
            "agent_harness.agents.lamponne.LamponneExecutor.execute",
            new_callable=AsyncMock,
            return_value="Execution done.",
        )

        with _all_patches(retrieve_patch, execute_patch) as mocks:
            mock_retrieve = mocks["_retrieve_semantic_patterns"]
            mock_execute = mocks["execute"]

            input_data = AgentLoopInput(
                agent_name="lamponne",
                domain="dce",
                operativo_id="op-le-1",
                task_message='{"steps": []}',
                available_tools=["discover_api", "execute_api"],
                max_turns=5,
            )
            await lamponne_execute(input_data)

            mock_retrieve.assert_called_once()
            call_kwargs = mock_execute.call_args[1]
            assert call_kwargs["semantic_patterns"] == ["[pattern] extraction order matters"]


class TestSantosQAReviewReceivesPatterns:
    """Verify santos_qa_review retrieves and passes semantic patterns."""

    @pytest.mark.asyncio
    async def test_santos_qa_review_calls_retrieve_patterns(self) -> None:
        mock_report = QAReport(
            operativo_id="op-qa-1",
            checks=[
                QACheck(
                    field="product_name",
                    expected="X",
                    actual="X",
                    severity=Severity.INFO,
                    auto_correctable=False,
                ),
            ],
        )

        retrieve_patch = patch(
            f"{_IMPL}._retrieve_semantic_patterns",
            new_callable=AsyncMock,
            return_value=["[error] common mismatch in HS codes"],
        )
        review_patch = patch(
            "agent_harness.agents.qa_reviewer.SantosQAReviewer.review",
            new_callable=AsyncMock,
            return_value=mock_report,
        )

        with _all_patches(retrieve_patch, review_patch) as mocks:
            mock_retrieve = mocks["_retrieve_semantic_patterns"]
            mock_review = mocks["review"]

            input_data = QAReviewInput(
                operativo_id="op-qa-1",
                domain="dce",
                input_snapshot_json='{"fields": {}}',
                raw_output_json='{"result": {}}',
            )
            await santos_qa_review(input_data)

            mock_retrieve.assert_called_once()
            call_kwargs = mock_review.call_args[1]
            assert call_kwargs["semantic_patterns"] == ["[error] common mismatch in HS codes"]


class TestRavennaSynthesizeReceivesPatterns:
    """Verify ravenna_synthesize retrieves and passes semantic patterns."""

    @pytest.mark.asyncio
    async def test_ravenna_synthesize_calls_retrieve_patterns(self) -> None:
        retrieve_patch = patch(
            f"{_IMPL}._retrieve_semantic_patterns",
            new_callable=AsyncMock,
            return_value=["[pattern] always include HS code in summary"],
        )
        synthesize_patch = patch(
            "agent_harness.agents.ravenna.RavennaSynthesizer.synthesize",
            new_callable=AsyncMock,
            return_value='{"status": "COMPLETED"}',
        )

        with _all_patches(retrieve_patch, synthesize_patch) as mocks:
            mock_retrieve = mocks["_retrieve_semantic_patterns"]
            mock_synthesize = mocks["synthesize"]

            input_data = SynthesizerInput(
                operativo_id="op-rs-1",
                domain="dce",
                progress_entries="Phase 1: done",
                raw_output_json='{"execution": "done"}',
                qa_report_json='{"checks": []}',
                caller_id="user-001",
            )
            await ravenna_synthesize(input_data)

            mock_retrieve.assert_called_once()
            call_kwargs = mock_synthesize.call_args[1]
            assert call_kwargs["semantic_patterns"] == ["[pattern] always include HS code in summary"]


class TestRetrieveSemanticPatterns:
    """Test the _retrieve_semantic_patterns helper directly."""

    @pytest.mark.asyncio
    async def test_combines_recall_and_bulletin_patterns(self) -> None:
        from agent_harness.activities.implementations import _retrieve_semantic_patterns

        mock_recall = MagicMock()
        mock_recall.retrieve_patterns = AsyncMock(
            return_value=["[fact] recall pattern 1", "[pattern] recall pattern 2"]
        )

        mock_bulletin = MagicMock()
        mock_bulletin.get_pattern_strings.return_value = ["[bulletin] cross-session insight"]

        with (
            patch(f"{_IMPL}.get_memory_recall", return_value=mock_recall),
            patch(f"{_IMPL}.get_bulletin_store", return_value=mock_bulletin),
        ):
            result = await _retrieve_semantic_patterns("dce", "test query")

            assert result == [
                "[fact] recall pattern 1",
                "[pattern] recall pattern 2",
                "[bulletin] cross-session insight",
            ]
            mock_recall.retrieve_patterns.assert_called_once_with("dce", "test query", top_k=5)
            mock_bulletin.get_pattern_strings.assert_called_once_with("dce")

    @pytest.mark.asyncio
    async def test_empty_when_no_patterns(self) -> None:
        from agent_harness.activities.implementations import _retrieve_semantic_patterns

        mock_recall = MagicMock()
        mock_recall.retrieve_patterns = AsyncMock(return_value=[])

        mock_bulletin = MagicMock()
        mock_bulletin.get_pattern_strings.return_value = []

        with (
            patch(f"{_IMPL}.get_memory_recall", return_value=mock_recall),
            patch(f"{_IMPL}.get_bulletin_store", return_value=mock_bulletin),
        ):
            result = await _retrieve_semantic_patterns("dce", "query")
            assert result == []
