"""Tests for investigator activity types."""

import pytest

from agent_harness.activities.investigator import (
    InvestigatorInput,
    InvestigatorOutput,
    InputSnapshot,
)


class TestInvestigatorInput:
    def test_creation(self):
        inp = InvestigatorInput(
            operativo_id="op-123",
            domain="dce",
            pdf_path="/path/to/file.pdf",
            pdf_filename="file.pdf",
        )
        assert inp.operativo_id == "op-123"
        assert inp.domain == "dce"

    def test_frozen(self):
        inp = InvestigatorInput("op-1", "dce", "/p.pdf", "p.pdf")
        with pytest.raises(AttributeError):
            inp.domain = "has"


class TestInvestigatorOutput:
    def test_creation(self):
        out = InvestigatorOutput(
            operativo_id="op-123",
            input_snapshot_json='{"fields": {}}',
            injection_risk="none",
            phase_result="Phase 2 complete",
        )
        assert out.operativo_id == "op-123"
        assert out.halted is False

    def test_halted_output(self):
        out = InvestigatorOutput(
            operativo_id="op-1",
            input_snapshot_json="{}",
            injection_risk="high",
            phase_result="HALTED: injection detected",
            halted=True,
        )
        assert out.halted is True
        assert out.injection_risk == "high"

    def test_frozen(self):
        out = InvestigatorOutput("op-1", "{}", "none", "done")
        with pytest.raises(AttributeError):
            out.halted = True


class TestInputSnapshot:
    def test_creation(self):
        snap = InputSnapshot(
            operativo_id="op-123",
            pdf_filename="test.pdf",
            injection_scan_risk="none",
            structured_fields={"product_name": "Widget"},
            raw_text_hash="sha256:abc123",
        )
        assert snap.operativo_id == "op-123"
        assert snap.structured_fields["product_name"] == "Widget"

    def test_frozen(self):
        snap = InputSnapshot("op-1", "f.pdf", "none", {}, "sha256:x")
        with pytest.raises(AttributeError):
            snap.operativo_id = "changed"
