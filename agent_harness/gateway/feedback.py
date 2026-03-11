"""Feedback API models."""
from pydantic import BaseModel
from agent_harness.core.feedback import FeedbackAction


class FeedbackRequest(BaseModel):
    action: FeedbackAction
    corrected_verdict: str | None = None
    corrected_citations: list[str] = []
    reviewer_notes: str = ""


class FeedbackResponse(BaseModel):
    status: str
    operativo_id: str
