"""Tests for planner activity types."""

from __future__ import annotations

import pytest

from agent_harness.activities.planner import PlannerInput, PlannerOutput
from agent_harness.core.plan import PhaseResult
from agent_harness.core.operativo import Phase


class TestPlannerInput:
    """Tests for PlannerInput frozen dataclass."""

    def test_creation(self):
        inp = PlannerInput(
            operativo_id="op-100",
            domain="dce",
            pdf_description="Certificate of conformity for widget X",
        )
        assert inp.operativo_id == "op-100"
        assert inp.domain == "dce"
        assert inp.pdf_description == "Certificate of conformity for widget X"

    def test_frozen(self):
        inp = PlannerInput(
            operativo_id="op-100",
            domain="dce",
            pdf_description="desc",
        )
        with pytest.raises(AttributeError):
            inp.operativo_id = "op-999"


class TestPlannerOutput:
    """Tests for PlannerOutput frozen dataclass."""

    def test_creation(self):
        phase_result = PhaseResult(
            phase=Phase.PLAN,
            agent="santos",
            field_report="Plan created with 3 steps.",
        )
        out = PlannerOutput(
            operativo_id="op-100",
            plan_json='{"steps": []}',
            phase_result=phase_result,
        )
        assert out.operativo_id == "op-100"
        assert out.plan_json == '{"steps": []}'
        assert out.phase_result.agent == "santos"

    def test_frozen(self):
        phase_result = PhaseResult(
            phase=Phase.PLAN,
            agent="santos",
            field_report="Done.",
        )
        out = PlannerOutput(
            operativo_id="op-100",
            plan_json="{}",
            phase_result=phase_result,
        )
        with pytest.raises(AttributeError):
            out.plan_json = "changed"
