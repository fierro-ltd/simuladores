"""Tests for feedback processing activities."""
from __future__ import annotations

import pytest

from agent_harness.activities.feedback_activities import (
    extract_lesson_activity,
    store_lesson_activity,
)


@pytest.mark.asyncio
async def test_extract_lesson_returns_structured_output():
    """extract_lesson_activity returns a dict with expected keys."""
    input_data = {
        "operativo_id": "dce-001",
        "domain": "dce",
        "original_verdict": "FAIL",
        "corrected_verdict": "PASS",
        "reviewer_notes": "Section 4.2 was actually compliant",
    }
    result = await extract_lesson_activity(input_data)
    assert result["what_changed"] == "Verdict changed from FAIL to PASS"
    assert result["what_it_implies"] == "Section 4.2 was actually compliant"
    assert result["domain"] == "dce"
    assert result["operativo_id"] == "dce-001"
    assert result["confidence"] == 0.8


@pytest.mark.asyncio
async def test_store_lesson_completes():
    """store_lesson_activity completes without error."""
    input_data = {
        "domain": "dce",
        "lesson": {
            "what_changed": "Verdict changed",
            "what_it_implies": "Stricter checks needed",
        },
    }
    # Should complete without raising
    result = await store_lesson_activity(input_data)
    assert result is None
