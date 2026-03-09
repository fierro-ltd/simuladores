"""Tests for Cortex Bulletin workflow types."""

from __future__ import annotations

import pytest

from agent_harness.workflows.cortex import (
    CortexBulletinWorkflow,
    CortexScheduleInput,
    CortexScheduleOutput,
)


class TestCortexScheduleInput:
    def test_defaults(self):
        inp = CortexScheduleInput(domain="dce")
        assert inp.domain == "dce"
        assert inp.max_patterns == 20
        assert inp.max_tokens == 500

    def test_custom_values(self):
        inp = CortexScheduleInput(domain="has", max_patterns=10, max_tokens=300)
        assert inp.domain == "has"
        assert inp.max_patterns == 10
        assert inp.max_tokens == 300

    def test_frozen(self):
        inp = CortexScheduleInput(domain="dce")
        with pytest.raises(AttributeError):
            inp.domain = "other"  # type: ignore[misc]


class TestCortexScheduleOutput:
    def test_creation(self):
        out = CortexScheduleOutput(
            domain="dce",
            pattern_count=5,
            bulletin_summary="Key patterns identified.",
            generated_at="2026-02-22T10:00:00+00:00",
        )
        assert out.domain == "dce"
        assert out.pattern_count == 5
        assert out.bulletin_summary == "Key patterns identified."
        assert out.generated_at == "2026-02-22T10:00:00+00:00"

    def test_frozen(self):
        out = CortexScheduleOutput(
            domain="dce",
            pattern_count=0,
            bulletin_summary="",
            generated_at="2026-02-22T10:00:00+00:00",
        )
        with pytest.raises(AttributeError):
            out.domain = "other"  # type: ignore[misc]


class TestCortexBulletinWorkflow:
    def test_workflow_class_exists(self):
        """Verify the workflow class is properly decorated and importable."""
        assert hasattr(CortexBulletinWorkflow, "run")
