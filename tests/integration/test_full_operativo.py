"""Tests for full operativo lifecycle (Phases 0-6)."""

import pytest

from agent_harness.workflows.operativo_workflow import CPCWorkflow, WorkflowConfig
from agent_harness.activities.planner import PlannerInput
from agent_harness.activities.agent_loop import AgentLoopInput
from agent_harness.activities.investigator import InvestigatorInput
from agent_harness.activities.qa_review import QAReviewInput
from agent_harness.activities.post_job import PostJobInput
from agent_harness.activities.synthesizer import SynthesizerInput
from agent_harness.domains.dce.operativo import CPCOperativoInput, CPCOperativoOutput
from agent_harness.core.operativo import OperativoStatus


class TestWorkflowConfigExtended:
    def test_new_timeout_defaults(self):
        config = WorkflowConfig()
        assert config.investigate_timeout_seconds == 1800
        assert config.qa_timeout_seconds == 1800
        assert config.post_job_timeout_seconds == 300
        assert config.max_correction_attempts == 3

    def test_custom_qa_config(self):
        config = WorkflowConfig(qa_timeout_seconds=600, max_correction_attempts=5)
        assert config.qa_timeout_seconds == 600
        assert config.max_correction_attempts == 5

    def test_synthesize_timeout_default(self):
        config = WorkflowConfig()
        assert config.synthesize_timeout_seconds == 1800

    def test_custom_synthesize_timeout(self):
        config = WorkflowConfig(synthesize_timeout_seconds=240)
        assert config.synthesize_timeout_seconds == 240


class TestCPCWorkflowPhase2:
    """Phase 2: Medina investigation."""

    def _make_input(self):
        return CPCOperativoInput(
            pdf_path="/path/to/test.pdf",
            pdf_filename="test.pdf",
            caller_id="user-1",
        )

    def test_build_investigate_input(self):
        wf = CPCWorkflow()
        inp = self._make_input()
        result = wf.build_investigate_input("op-123", inp)
        assert isinstance(result, InvestigatorInput)
        assert result.operativo_id == "op-123"
        assert result.domain == "dce"
        assert result.pdf_path == "/path/to/test.pdf"
        assert result.pdf_filename == "test.pdf"

    def test_investigate_uses_input_pdf(self):
        wf = CPCWorkflow()
        inp = CPCOperativoInput(
            pdf_path="/other/doc.pdf",
            pdf_filename="doc.pdf",
            caller_id="user-2",
        )
        result = wf.build_investigate_input("op-456", inp)
        assert result.pdf_path == "/other/doc.pdf"
        assert result.pdf_filename == "doc.pdf"


class TestCPCWorkflowPhase4:
    """Phase 4: Santos QA review."""

    def test_build_qa_input(self):
        wf = CPCWorkflow()
        result = wf.build_qa_input(
            "op-123",
            input_snapshot_json='{"fields": {}}',
            raw_output_json='{"result": {}}',
        )
        assert isinstance(result, QAReviewInput)
        assert result.operativo_id == "op-123"
        assert result.domain == "dce"
        assert result.input_snapshot_json == '{"fields": {}}'
        assert result.raw_output_json == '{"result": {}}'
        assert result.max_correction_attempts == 3

    def test_qa_respects_config(self):
        wf = CPCWorkflow(WorkflowConfig(max_correction_attempts=5))
        result = wf.build_qa_input("op-1", "{}", "{}")
        assert result.max_correction_attempts == 5

    def test_qa_needs_review_output(self):
        wf = CPCWorkflow()
        output = wf.build_output("op-1", "Issues remain.", OperativoStatus.NEEDS_REVIEW)
        assert output.status == OperativoStatus.NEEDS_REVIEW


class TestCPCWorkflowPhase5:
    """Phase 5: Ravenna synthesis."""

    def test_build_synthesize_input(self):
        wf = CPCWorkflow()
        result = wf.build_synthesize_input(
            operativo_id="op-123",
            progress_entries="# PROGRESS\n...",
            raw_output_json='{"result": {}}',
            qa_report_json='{"checks": []}',
            caller_id="user-1",
        )
        assert isinstance(result, SynthesizerInput)
        assert result.operativo_id == "op-123"
        assert result.domain == "dce"
        assert result.caller_id == "user-1"

    def test_synthesize_preserves_all_inputs(self):
        wf = CPCWorkflow()
        result = wf.build_synthesize_input(
            operativo_id="op-1",
            progress_entries="progress",
            raw_output_json="output",
            qa_report_json="qa",
            caller_id="u1",
        )
        assert result.progress_entries == "progress"
        assert result.raw_output_json == "output"
        assert result.qa_report_json == "qa"


class TestCPCWorkflowPhase6:
    """Phase 6: Post-job learning."""

    def test_build_post_job_input(self):
        wf = CPCWorkflow()
        result = wf.build_post_job_input("op-123", "# PROGRESS\n## Phase 1\n...")
        assert isinstance(result, PostJobInput)
        assert result.operativo_id == "op-123"
        assert result.domain == "dce"
        assert "PROGRESS" in result.session_progress

    def test_post_job_preserves_full_progress(self):
        progress = "Phase 1\nPhase 2\nPhase 3\nPhase 4\nPhase 5"
        wf = CPCWorkflow()
        result = wf.build_post_job_input("op-1", progress)
        assert result.session_progress == progress


class TestFullLifecycleTypes:
    """Verify the full lifecycle type chain works end-to-end."""

    def test_all_phases_produce_correct_types(self):
        wf = CPCWorkflow()
        inp = CPCOperativoInput(
            pdf_path="/path/test.pdf",
            pdf_filename="test.pdf",
            caller_id="user-1",
        )

        # Phase 1
        plan_input = wf.build_plan_input("op-full", inp)
        assert isinstance(plan_input, PlannerInput)

        # Phase 2
        investigate_input = wf.build_investigate_input("op-full", inp)
        assert isinstance(investigate_input, InvestigatorInput)

        # Phase 3
        execute_input = wf.build_execute_input("op-full", '{"steps": []}')
        assert isinstance(execute_input, AgentLoopInput)

        # Phase 4
        qa_input = wf.build_qa_input("op-full", "{}", "{}")
        assert isinstance(qa_input, QAReviewInput)

        # Phase 5
        synthesize_input = wf.build_synthesize_input(
            "op-full", "progress", "{}", "{}", "user-1"
        )
        assert isinstance(synthesize_input, SynthesizerInput)

        # Phase 6
        post_job_input = wf.build_post_job_input("op-full", "progress...")
        assert isinstance(post_job_input, PostJobInput)

        # Output
        output = wf.build_output("op-full", "Done.")
        assert isinstance(output, CPCOperativoOutput)
        assert output.status == OperativoStatus.COMPLETED

    def test_operativo_ids_thread_through(self):
        wf = CPCWorkflow()
        op_id = "op-thread-test"
        inp = CPCOperativoInput(
            pdf_path="/p.pdf", pdf_filename="p.pdf", caller_id="u1"
        )
        assert wf.build_plan_input(op_id, inp).operativo_id == op_id
        assert wf.build_investigate_input(op_id, inp).operativo_id == op_id
        assert wf.build_execute_input(op_id, "{}").operativo_id == op_id
        assert wf.build_qa_input(op_id, "{}", "{}").operativo_id == op_id
        assert wf.build_synthesize_input(op_id, "", "{}", "{}", "u1").operativo_id == op_id
        assert wf.build_post_job_input(op_id, "").operativo_id == op_id
        assert wf.build_output(op_id, "").operativo_id == op_id


class TestExportsIntegration:
    """Verify all new types are accessible from package exports."""

    def test_activities_exports(self):
        from agent_harness.activities import (
            QAReviewInput,
            QAReviewOutput,
            PostJobInput,
            PostJobOutput,
        )
        assert QAReviewInput is not None
        assert PostJobInput is not None

    def test_agents_exports(self):
        from agent_harness.agents import (
            SANTOS_QA_IDENTITY,
            QACheck,
            QAReport,
        )
        assert SANTOS_QA_IDENTITY is not None
        assert QACheck is not None
        assert QAReport is not None

    def test_synthesizer_exports(self):
        from agent_harness.activities import (
            SynthesizerInput,
            SynthesizerOutput,
            QASummary,
        )
        assert SynthesizerInput is not None

    def test_ravenna_exports(self):
        from agent_harness.agents import (
            RAVENNA_SYSTEM_IDENTITY,
            RAVENNA_TOOLS,
        )
        assert RAVENNA_SYSTEM_IDENTITY is not None
