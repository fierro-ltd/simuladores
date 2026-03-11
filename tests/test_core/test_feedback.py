"""Tests for feedback schema."""
from __future__ import annotations

from datetime import datetime

from agent_harness.core.feedback import (
    ExtractedLesson,
    FeedbackAction,
    OperativoFeedback,
)


def test_feedback_action_values():
    """FeedbackAction enum contains expected string values."""
    assert FeedbackAction.ACCEPTED == "accepted"
    assert FeedbackAction.CORRECTED == "corrected"
    assert FeedbackAction.ESCALATED == "escalated"
    assert FeedbackAction.REJECTED == "rejected"


def test_operativo_feedback_creation():
    """OperativoFeedback can be created with all required fields."""
    fb = OperativoFeedback(
        operativo_id="dce-001",
        domain="dce",
        action=FeedbackAction.CORRECTED,
        original_verdict="FAIL",
        corrected_verdict="PASS",
        original_citations=["section 4.1"],
        corrected_citations=["section 4.1", "section 4.2"],
        reviewer_notes="Missing citation for section 4.2",
    )
    assert fb.operativo_id == "dce-001"
    assert fb.domain == "dce"
    assert fb.action == FeedbackAction.CORRECTED
    assert fb.corrected_verdict == "PASS"
    assert isinstance(fb.timestamp, datetime)


def test_extracted_lesson_defaults():
    """ExtractedLesson has correct defaults for optional fields."""
    lesson = ExtractedLesson(
        what_changed="Verdict changed",
        what_it_implies="Need stricter checks",
        domain="dce",
        operativo_id="dce-001",
        confidence=0.9,
    )
    assert lesson.example_quote is None
    assert lesson.confidence == 0.9
    assert lesson.domain == "dce"
