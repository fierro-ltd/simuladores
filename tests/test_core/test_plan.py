"""Tests for plan types."""

from agent_harness.core.operativo import Phase
from agent_harness.core.plan import AgentTask, ExecutionPlan, PhaseResult


class TestAgentTask:
    def test_creation(self):
        task = AgentTask(agent="santos", action="plan", params={"key": "value"})
        assert task.agent == "santos"
        assert task.action == "plan"
        assert task.params == {"key": "value"}

    def test_frozen(self):
        task = AgentTask(agent="santos", action="plan")
        try:
            task.agent = "other"  # type: ignore[misc]
            assert False, "Should have raised"
        except AttributeError:
            pass

    def test_default_params(self):
        task = AgentTask(agent="santos", action="plan")
        assert task.params == {}


class TestExecutionPlan:
    def test_creation(self):
        plan = ExecutionPlan(
            operativo_id="op-1",
            tasks=[AgentTask(agent="santos", action="plan")],
        )
        assert plan.operativo_id == "op-1"
        assert len(plan.tasks) == 1

    def test_default_empty_tasks(self):
        plan = ExecutionPlan(operativo_id="op-1")
        assert plan.tasks == []


class TestPhaseResult:
    def test_field_report_truncation(self):
        long_report = "x" * 1000
        result = PhaseResult(phase=Phase.PLAN, agent="santos", field_report=long_report)
        assert len(result.field_report) == 500

    def test_short_report_not_truncated(self):
        result = PhaseResult(phase=Phase.PLAN, agent="santos", field_report="short report")
        assert result.field_report == "short report"

    def test_exact_500_not_truncated(self):
        report = "x" * 500
        result = PhaseResult(phase=Phase.PLAN, agent="santos", field_report=report)
        assert len(result.field_report) == 500
