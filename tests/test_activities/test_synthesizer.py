"""Tests for synthesizer activity types."""

import pytest

from agent_harness.activities.synthesizer import (
    SynthesizerInput,
    SynthesizerOutput,
    QASummary,
)


class TestSynthesizerInput:
    def test_creation(self):
        inp = SynthesizerInput(
            operativo_id="op-123",
            domain="dce",
            progress_entries="# Progress",
            raw_output_json='{"result": {}}',
            qa_report_json='{"checks": []}',
            caller_id="user-1",
        )
        assert inp.operativo_id == "op-123"
        assert inp.domain == "dce"
        assert inp.caller_id == "user-1"

    def test_frozen(self):
        inp = SynthesizerInput(
            operativo_id="op-1", domain="dce",
            progress_entries="", raw_output_json="{}",
            qa_report_json="{}", caller_id="u1",
        )
        with pytest.raises(AttributeError):
            inp.operativo_id = "changed"


class TestQASummary:
    def test_creation(self):
        summary = QASummary(
            total_checks=15,
            blocking=0,
            warnings=2,
            info=5,
            corrections_applied=1,
        )
        assert summary.total_checks == 15
        assert summary.blocking == 0
        assert summary.warnings == 2
        assert summary.info == 5
        assert summary.corrections_applied == 1

    def test_frozen(self):
        summary = QASummary(
            total_checks=10, blocking=1, warnings=0,
            info=3, corrections_applied=0,
        )
        with pytest.raises(AttributeError):
            summary.total_checks = 20

    def test_zero_summary(self):
        summary = QASummary(
            total_checks=0, blocking=0, warnings=0,
            info=0, corrections_applied=0,
        )
        assert summary.total_checks == 0


class TestSynthesizerOutput:
    def test_creation(self):
        out = SynthesizerOutput(
            operativo_id="op-123",
            structured_result_json='{"status": "COMPLETED"}',
            report_url="gs://bucket/report.pdf",
            phase_result="Phase 5 complete.",
        )
        assert out.operativo_id == "op-123"
        assert out.delivery_permitted is True
        assert "COMPLETED" in out.structured_result_json

    def test_delivery_denied(self):
        out = SynthesizerOutput(
            operativo_id="op-1",
            structured_result_json="{}",
            report_url="",
            phase_result="Denied.",
            delivery_permitted=False,
        )
        assert out.delivery_permitted is False

    def test_frozen(self):
        out = SynthesizerOutput(
            operativo_id="op-1",
            structured_result_json="{}",
            report_url="",
            phase_result="done",
        )
        with pytest.raises(AttributeError):
            out.operativo_id = "changed"
