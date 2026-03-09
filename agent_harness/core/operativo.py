"""Core operativo types: Phase, Status, Severity, QAIssue, OperativoResult."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum


class Phase(IntEnum):
    """Operativo execution phases, ordered by sequence."""

    INTAKE = 0
    PLAN = 1
    INVESTIGATE = 2
    EXECUTE = 3
    QA = 4
    SYNTHESIZE = 5
    POST_JOB = 6


class OperativoStatus(StrEnum):
    """Status of an operativo."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"

    @property
    def is_terminal(self) -> bool:
        """Whether this status represents a terminal state."""
        return self in {
            OperativoStatus.COMPLETED,
            OperativoStatus.FAILED,
            OperativoStatus.NEEDS_REVIEW,
        }


class Severity(IntEnum):
    """QA issue severity levels."""

    INFO = 0
    WARNING = 1
    BLOCKING = 2


@dataclass(frozen=True)
class QAIssue:
    """A QA issue found during quality assurance."""

    field: str
    message: str
    severity: Severity


@dataclass
class OperativoResult:
    """Result of an operativo execution."""

    operativo_id: str
    status: OperativoStatus
    structured_result: dict | None = None
    report_url: str | None = None
    qa_issues: list[QAIssue] = field(default_factory=list)

    @property
    def has_blocking_issues(self) -> bool:
        """Whether any QA issue is blocking."""
        return any(issue.severity == Severity.BLOCKING for issue in self.qa_issues)
