"""Execution plan types: AgentTask, ExecutionPlan, PhaseResult."""

from __future__ import annotations

from dataclasses import dataclass, field

from agent_harness.core.operativo import Phase

_FIELD_REPORT_MAX_LEN = 500


@dataclass(frozen=True)
class AgentTask:
    """A single task assigned to an agent."""

    agent: str
    action: str
    params: dict = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    """Ordered list of tasks for an operativo."""

    operativo_id: str
    tasks: list[AgentTask] = field(default_factory=list)


@dataclass
class PhaseResult:
    """Result of a single phase execution, written to PROGRESS.md."""

    phase: Phase
    agent: str
    field_report: str

    def __post_init__(self) -> None:
        if len(self.field_report) > _FIELD_REPORT_MAX_LEN:
            self.field_report = self.field_report[:_FIELD_REPORT_MAX_LEN]
