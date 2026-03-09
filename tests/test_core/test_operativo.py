"""Tests for core operativo types."""

from agent_harness.core.operativo import (
    OperativoResult,
    OperativoStatus,
    Phase,
    QAIssue,
    Severity,
)


class TestPhase:
    def test_all_seven_phases_exist(self):
        assert len(Phase) == 7

    def test_phase_ordering(self):
        assert Phase.INTAKE < Phase.PLAN < Phase.INVESTIGATE < Phase.EXECUTE
        assert Phase.EXECUTE < Phase.QA < Phase.SYNTHESIZE < Phase.POST_JOB

    def test_phase_values(self):
        assert Phase.INTAKE == 0
        assert Phase.POST_JOB == 6


class TestOperativoStatus:
    def test_terminal_statuses(self):
        for status in (
            OperativoStatus.COMPLETED,
            OperativoStatus.FAILED,
            OperativoStatus.NEEDS_REVIEW,
        ):
            assert status.is_terminal is True

    def test_non_terminal_statuses(self):
        for status in (OperativoStatus.PENDING, OperativoStatus.RUNNING):
            assert status.is_terminal is False


class TestSeverity:
    def test_severity_ordering(self):
        assert Severity.INFO < Severity.WARNING < Severity.BLOCKING


class TestQAIssue:
    def test_frozen(self):
        issue = QAIssue(field="name", message="missing", severity=Severity.BLOCKING)
        assert issue.field == "name"
        try:
            issue.field = "other"  # type: ignore[misc]
            assert False, "Should have raised"
        except AttributeError:
            pass


class TestOperativoResult:
    def test_has_blocking_issues_true(self):
        result = OperativoResult(
            operativo_id="op-1",
            status=OperativoStatus.COMPLETED,
            qa_issues=[QAIssue(field="x", message="bad", severity=Severity.BLOCKING)],
        )
        assert result.has_blocking_issues is True

    def test_has_blocking_issues_false_with_non_blocking(self):
        result = OperativoResult(
            operativo_id="op-1",
            status=OperativoStatus.COMPLETED,
            qa_issues=[QAIssue(field="x", message="ok", severity=Severity.WARNING)],
        )
        assert result.has_blocking_issues is False

    def test_has_blocking_issues_false_empty(self):
        result = OperativoResult(
            operativo_id="op-1",
            status=OperativoStatus.COMPLETED,
        )
        assert result.has_blocking_issues is False

    def test_default_fields(self):
        result = OperativoResult(operativo_id="op-1", status=OperativoStatus.PENDING)
        assert result.structured_result is None
        assert result.report_url is None
        assert result.qa_issues == []
