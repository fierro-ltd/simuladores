"""Tests for DCEWorkflow."""

import pytest

from agent_harness.workflows.operativo_workflow import (
    E2E_FAST_WORKFLOW_CONFIG,
    CPCWorkflow,
    WorkflowConfig,
)
from agent_harness.activities.planner import PlannerInput
from agent_harness.activities.agent_loop import AgentLoopInput
from agent_harness.domains.dce.operativo import CPCOperativoInput, CPCOperativoOutput
from agent_harness.core.operativo import OperativoStatus


class TestWorkflowConfig:
    def test_defaults(self):
        config = WorkflowConfig()
        assert config.plan_timeout_seconds == 1800
        assert config.execute_timeout_seconds == 1800
        assert config.max_execution_turns == 10

    def test_custom(self):
        config = WorkflowConfig(plan_timeout_seconds=60, max_execution_turns=5)
        assert config.plan_timeout_seconds == 60
        assert config.max_execution_turns == 5


class TestCPCWorkflow:
    def _make_input(self):
        return CPCOperativoInput(
            pdf_path="/path/to/test.pdf",
            pdf_filename="test.pdf",
            caller_id="user-1",
        )

    def test_build_plan_input(self):
        wf = CPCWorkflow()
        inp = self._make_input()
        plan_input = wf.build_plan_input("op-123", inp)
        assert isinstance(plan_input, PlannerInput)
        assert plan_input.operativo_id == "op-123"
        assert plan_input.domain == "dce"
        assert "test.pdf" in plan_input.pdf_description

    def test_build_execute_input(self):
        wf = CPCWorkflow()
        exec_input = wf.build_execute_input("op-123", '{"steps": []}')
        assert isinstance(exec_input, AgentLoopInput)
        assert exec_input.agent_name == "lamponne"
        assert exec_input.domain == "dce"
        assert "steps" in exec_input.task_message
        assert len(exec_input.available_tools) == 2  # discover + execute

    def test_build_output_completed(self):
        wf = CPCWorkflow()
        output = wf.build_output("op-123", "All done.")
        assert isinstance(output, CPCOperativoOutput)
        assert output.operativo_id == "op-123"
        assert output.status == OperativoStatus.COMPLETED
        assert output.structured_result["response"] == "All done."

    def test_build_output_needs_review(self):
        wf = CPCWorkflow()
        output = wf.build_output("op-123", "Issues found.", OperativoStatus.NEEDS_REVIEW)
        assert output.status == OperativoStatus.NEEDS_REVIEW

    def test_custom_config_affects_execution(self):
        wf = CPCWorkflow(WorkflowConfig(max_execution_turns=3))
        exec_input = wf.build_execute_input("op-1", "{}")
        assert exec_input.max_turns == 3

    def test_e2e_fast_mode_default_false(self):
        inp = self._make_input()
        assert inp.e2e_fast_mode is False

    def test_e2e_fast_config_has_reduced_limits(self):
        default = WorkflowConfig()
        assert E2E_FAST_WORKFLOW_CONFIG.max_execution_turns < default.max_execution_turns
        assert E2E_FAST_WORKFLOW_CONFIG.max_correction_attempts < default.max_correction_attempts
        assert E2E_FAST_WORKFLOW_CONFIG.execute_timeout_seconds < default.execute_timeout_seconds

    def test_build_execute_input_uses_runtime_config_when_provided(self):
        wf = CPCWorkflow()
        exec_input = wf.build_execute_input("op-123", "{}", runtime_config=E2E_FAST_WORKFLOW_CONFIG)
        assert exec_input.max_turns == E2E_FAST_WORKFLOW_CONFIG.max_execution_turns
