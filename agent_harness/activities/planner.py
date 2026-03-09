"""Planner activity input/output types for Temporal activities."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PlannerInput:
    """Input for the planner activity."""

    operativo_id: str
    domain: str
    pdf_description: str


@dataclass(frozen=True)
class PlannerOutput:
    """Output from the planner activity."""

    operativo_id: str
    plan_json: str
    phase_result: str
