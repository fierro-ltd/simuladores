"""Feedback processing workflow — extracts lessons from human corrections."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from agent_harness.core.feedback import FeedbackAction, OperativoFeedback


@dataclass
class FeedbackWorkflowInput:
    operativo_id: str
    domain: str
    action: str
    original_verdict: str
    corrected_verdict: str | None = None
    corrected_citations: list[str] | None = None
    reviewer_notes: str = ""


@workflow.defn
class FeedbackProcessingWorkflow:
    """Processes human feedback and extracts lessons."""

    @workflow.run
    async def run(self, input: FeedbackWorkflowInput) -> dict:
        if input.action != FeedbackAction.CORRECTED:
            return {"status": "logged", "lesson_extracted": False}

        # Extract lesson via activity
        lesson = await workflow.execute_activity(
            "extract_lesson",
            input,
            start_to_close_timeout=timedelta(minutes=2),
        )

        # Store lesson via activity
        await workflow.execute_activity(
            "store_lesson",
            {"domain": input.domain, "lesson": lesson},
            start_to_close_timeout=timedelta(seconds=30),
        )

        return {"status": "processed", "lesson_extracted": True}
