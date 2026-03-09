"""Tests for IdpWorkflow."""

import pytest

from agent_harness.workflows.idp_workflow import (
    IdpWorkflow,
    IdpWorkflowConfig,
)
from agent_harness.activities.planner import PlannerInput
from agent_harness.activities.agent_loop import AgentLoopInput
from agent_harness.domains.idp.operativo import (
    IdpOperativoInput,
    IdpOperativoOutput,
)
from agent_harness.core.operativo import OperativoStatus


class TestIdpWorkflowConfig:
    def test_defaults(self):
        config = IdpWorkflowConfig()
        assert config.plan_timeout_seconds == 120
        assert config.execute_timeout_seconds == 600
        assert config.max_execution_turns == 10
        assert config.max_correction_attempts == 3

    def test_custom(self):
        config = IdpWorkflowConfig(plan_timeout_seconds=60, max_execution_turns=5)
        assert config.plan_timeout_seconds == 60
        assert config.max_execution_turns == 5


class TestIdpWorkflow:
    def _make_input(self):
        return IdpOperativoInput(
            product_description="Children's toy robot",
            caller_id="user-1",
            target_markets=["US", "EU"],
        )

    def test_build_plan_input(self):
        wf = IdpWorkflow()
        inp = self._make_input()
        plan_input = wf.build_plan_input("nav-123", inp)
        assert isinstance(plan_input, PlannerInput)
        assert plan_input.operativo_id == "nav-123"
        assert plan_input.domain == "idp"
        assert "Children's toy robot" in plan_input.pdf_description

    def test_build_execute_input(self):
        wf = IdpWorkflow()
        exec_input = wf.build_execute_input("nav-123", '{"steps": []}')
        assert isinstance(exec_input, AgentLoopInput)
        assert exec_input.agent_name == "lamponne"
        assert exec_input.domain == "idp"
        assert "steps" in exec_input.task_message
        assert len(exec_input.available_tools) == 2  # discover + execute

    def test_build_output_completed(self):
        wf = IdpWorkflow()
        output = wf.build_output("nav-123", "All done.")
        assert isinstance(output, IdpOperativoOutput)
        assert output.operativo_id == "nav-123"
        assert output.status == OperativoStatus.COMPLETED
        assert output.structured_result["response"] == "All done."

    def test_build_output_needs_review(self):
        wf = IdpWorkflow()
        output = wf.build_output("nav-123", "Issues found.", OperativoStatus.NEEDS_REVIEW)
        assert output.status == OperativoStatus.NEEDS_REVIEW

    def test_custom_config_affects_execution(self):
        wf = IdpWorkflow(IdpWorkflowConfig(max_execution_turns=3))
        exec_input = wf.build_execute_input("nav-1", "{}")
        assert exec_input.max_turns == 3

    def test_build_investigate_input_empty_paths(self):
        """IDP has no PDF — investigate input should have empty paths."""
        wf = IdpWorkflow()
        inp = self._make_input()
        inv_input = wf.build_investigate_input("nav-123", inp)
        assert inv_input.domain == "idp"
        assert inv_input.pdf_path == ""
        assert inv_input.pdf_filename == ""
