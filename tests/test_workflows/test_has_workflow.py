"""Tests for CEEWorkflow."""


from agent_harness.workflows.has_workflow import CEEWorkflow, CEEWorkflowConfig
from agent_harness.activities.planner import PlannerInput
from agent_harness.activities.agent_loop import AgentLoopInput
from agent_harness.domains.has.operativo import CEEOperativoInput, CEEOperativoOutput
from agent_harness.core.operativo import OperativoStatus


class TestCEEWorkflowConfig:
    def test_defaults(self):
        config = CEEWorkflowConfig()
        assert config.plan_timeout_seconds == 120
        assert config.execute_timeout_seconds == 600
        assert config.max_execution_turns == 10
        assert config.max_correction_attempts == 3

    def test_custom(self):
        config = CEEWorkflowConfig(plan_timeout_seconds=60, max_execution_turns=5)
        assert config.plan_timeout_seconds == 60
        assert config.max_execution_turns == 5


class TestCEEWorkflow:
    def _make_input(self):
        return CEEOperativoInput(
            document_path="/path/to/attestation.pdf",
            document_filename="attestation.pdf",
            caller_id="user-1",
            document_type="attestation",
        )

    def test_build_plan_input(self):
        wf = CEEWorkflow()
        inp = self._make_input()
        plan_input = wf.build_plan_input("op-123", inp)
        assert isinstance(plan_input, PlannerInput)
        assert plan_input.operativo_id == "op-123"
        assert plan_input.domain == "has"
        assert "attestation.pdf" in plan_input.pdf_description

    def test_build_execute_input(self):
        wf = CEEWorkflow()
        exec_input = wf.build_execute_input("op-123", '{"steps": []}')
        assert isinstance(exec_input, AgentLoopInput)
        assert exec_input.agent_name == "lamponne"
        assert exec_input.domain == "has"
        assert "steps" in exec_input.task_message
        assert len(exec_input.available_tools) == 2  # discover + execute

    def test_build_output_completed(self):
        wf = CEEWorkflow()
        output = wf.build_output("op-123", "All done.")
        assert isinstance(output, CEEOperativoOutput)
        assert output.operativo_id == "op-123"
        assert output.status == OperativoStatus.COMPLETED
        assert output.structured_result["response"] == "All done."

    def test_build_output_needs_review(self):
        wf = CEEWorkflow()
        output = wf.build_output("op-123", "Issues found.", OperativoStatus.NEEDS_REVIEW)
        assert output.status == OperativoStatus.NEEDS_REVIEW

    def test_custom_config_affects_execution(self):
        wf = CEEWorkflow(CEEWorkflowConfig(max_execution_turns=3))
        exec_input = wf.build_execute_input("op-1", "{}")
        assert exec_input.max_turns == 3
