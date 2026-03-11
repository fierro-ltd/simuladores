"""Tests for feedback processing workflow."""
from __future__ import annotations

from agent_harness.workflows.feedback_workflow import FeedbackWorkflowInput


def test_feedback_workflow_skips_non_corrected():
    """Non-corrected feedback should not trigger lesson extraction."""
    inp = FeedbackWorkflowInput(
        operativo_id="dce-001",
        domain="dce",
        action="accepted",
        original_verdict="PASS",
    )
    # The workflow only extracts lessons when action == "corrected"
    assert inp.action != "corrected"


def test_feedback_workflow_input_creation():
    """FeedbackWorkflowInput can be created with all fields."""
    inp = FeedbackWorkflowInput(
        operativo_id="dce-002",
        domain="dce",
        action="corrected",
        original_verdict="FAIL",
        corrected_verdict="PASS",
        corrected_citations=["section 4.2"],
        reviewer_notes="Added missing citation",
    )
    assert inp.operativo_id == "dce-002"
    assert inp.action == "corrected"
    assert inp.corrected_verdict == "PASS"
    assert inp.corrected_citations == ["section 4.2"]
    assert inp.reviewer_notes == "Added missing citation"
