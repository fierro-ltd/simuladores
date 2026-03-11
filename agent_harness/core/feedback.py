"""Feedback schema for human-in-the-loop learning."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class FeedbackAction(StrEnum):
    ACCEPTED = "accepted"
    CORRECTED = "corrected"
    ESCALATED = "escalated"
    REJECTED = "rejected"


@dataclass
class OperativoFeedback:
    operativo_id: str
    domain: str
    action: FeedbackAction
    original_verdict: str
    corrected_verdict: str | None
    original_citations: list[str]
    corrected_citations: list[str]
    reviewer_notes: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ExtractedLesson:
    """Structured lesson from comparing original vs. corrected output."""
    what_changed: str
    what_it_implies: str
    domain: str
    operativo_id: str
    confidence: float
    example_quote: str | None = None
