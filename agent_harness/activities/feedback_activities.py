"""Feedback processing activities."""
from __future__ import annotations

from temporalio import activity


@activity.defn(name="extract_lesson")
async def extract_lesson_activity(input: dict) -> dict:
    """Extract a structured lesson from feedback diff.

    In production, this calls Claude Haiku via instructor.
    For now, returns a structured lesson from the input.
    """
    return {
        "what_changed": f"Verdict changed from {input.get('original_verdict', '?')} to {input.get('corrected_verdict', '?')}",
        "what_it_implies": input.get("reviewer_notes", "No notes provided"),
        "domain": input.get("domain", "unknown"),
        "operativo_id": input.get("operativo_id", "unknown"),
        "confidence": 0.8,
    }


@activity.defn(name="store_lesson")
async def store_lesson_activity(input: dict) -> None:
    """Store extracted lesson in mem0.

    In production, this uses Mem0DomainMemory.add().
    For now, logs the lesson.
    """
    import logging
    logger = logging.getLogger(__name__)
    lesson = input.get("lesson", {})
    logger.info(
        "Stored lesson for domain=%s: %s",
        input.get("domain"), lesson.get("what_changed"),
    )
