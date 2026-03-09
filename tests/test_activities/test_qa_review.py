"""Tests for Santos QA review Temporal activity types."""

import pytest

from agent_harness.activities.qa_review import QAReviewInput, QAReviewOutput


class TestQAReviewInput:
    def test_creation(self):
        inp = QAReviewInput(
            operativo_id="op-123",
            domain="dce",
            input_snapshot_json='{"product": "Widget"}',
            raw_output_json='{"product": "Widget"}',
        )
        assert inp.operativo_id == "op-123"
        assert inp.domain == "dce"

    def test_default_max_attempts(self):
        inp = QAReviewInput(
            operativo_id="op-1",
            domain="dce",
            input_snapshot_json="{}",
            raw_output_json="{}",
        )
        assert inp.max_correction_attempts == 3

    def test_custom_max_attempts(self):
        inp = QAReviewInput(
            operativo_id="op-1",
            domain="dce",
            input_snapshot_json="{}",
            raw_output_json="{}",
            max_correction_attempts=5,
        )
        assert inp.max_correction_attempts == 5

    def test_frozen(self):
        inp = QAReviewInput(
            operativo_id="op-1",
            domain="dce",
            input_snapshot_json="{}",
            raw_output_json="{}",
        )
        with pytest.raises(AttributeError):
            inp.domain = "has"


class TestQAReviewOutput:
    def test_creation(self):
        out = QAReviewOutput(
            operativo_id="op-123",
            qa_report_json='{"checks": []}',
            corrections_applied=2,
            final_status="COMPLETED",
            phase_result="QA passed after 2 corrections",
        )
        assert out.operativo_id == "op-123"
        assert out.corrections_applied == 2
        assert out.final_status == "COMPLETED"

    def test_needs_review_status(self):
        out = QAReviewOutput(
            operativo_id="op-456",
            qa_report_json='{"checks": [{"severity": "BLOCKING"}]}',
            corrections_applied=3,
            final_status="NEEDS_REVIEW",
            phase_result="Max correction attempts reached",
        )
        assert out.final_status == "NEEDS_REVIEW"

    def test_frozen(self):
        out = QAReviewOutput(
            operativo_id="op-1",
            qa_report_json="{}",
            corrections_applied=0,
            final_status="COMPLETED",
            phase_result="OK",
        )
        with pytest.raises(AttributeError):
            out.final_status = "NEEDS_REVIEW"


class TestQAReviewInputVerifyChecklist:
    """Tests for the verify_checklist field on QAReviewInput."""

    def test_default_is_none(self):
        inp = QAReviewInput(
            operativo_id="op-1",
            domain="dce",
            input_snapshot_json="{}",
            raw_output_json="{}",
        )
        assert inp.verify_checklist is None

    def test_accepts_tuple_of_strings(self):
        items = ("Check A", "Check B")
        inp = QAReviewInput(
            operativo_id="op-1",
            domain="dce",
            input_snapshot_json="{}",
            raw_output_json="{}",
            verify_checklist=items,
        )
        assert inp.verify_checklist == items
        assert len(inp.verify_checklist) == 2

    def test_frozen_with_checklist(self):
        inp = QAReviewInput(
            operativo_id="op-1",
            domain="dce",
            input_snapshot_json="{}",
            raw_output_json="{}",
            verify_checklist=("Check A",),
        )
        with pytest.raises(AttributeError):
            inp.verify_checklist = ("Check B",)


class TestQAReviewInputCitationCompleteness:
    """Tests for citation_completeness_report_json on QAReviewInput."""

    def test_default_empty(self):
        inp = QAReviewInput(
            operativo_id="op-1",
            domain="dce",
            input_snapshot_json="{}",
            raw_output_json="{}",
        )
        assert inp.citation_completeness_report_json == ""

    def test_accepts_citation_report(self):
        report = '{"provided_citations": ["16 CFR Part 1303"], "web_verification_recommended": false}'
        inp = QAReviewInput(
            operativo_id="op-1",
            domain="dce",
            input_snapshot_json="{}",
            raw_output_json="{}",
            citation_completeness_report_json=report,
        )
        assert inp.citation_completeness_report_json == report
