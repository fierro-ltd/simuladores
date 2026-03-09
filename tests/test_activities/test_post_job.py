"""Tests for post-job learning Temporal activity types."""

import pytest

from agent_harness.activities.post_job import PostJobInput, PostJobOutput


class TestPostJobInput:
    def test_creation(self):
        inp = PostJobInput(
            operativo_id="op-123",
            domain="dce",
            session_progress="## Phase 1\nPlanning completed.",
        )
        assert inp.operativo_id == "op-123"
        assert inp.domain == "dce"
        assert "Phase 1" in inp.session_progress

    def test_frozen(self):
        inp = PostJobInput(
            operativo_id="op-1",
            domain="dce",
            session_progress="done",
        )
        with pytest.raises(AttributeError):
            inp.domain = "has"


class TestPostJobOutput:
    def test_creation(self):
        out = PostJobOutput(
            operativo_id="op-123",
            patterns_extracted=3,
            archived=True,
        )
        assert out.operativo_id == "op-123"
        assert out.patterns_extracted == 3
        assert out.archived is True

    def test_no_patterns(self):
        out = PostJobOutput(
            operativo_id="op-456",
            patterns_extracted=0,
            archived=True,
        )
        assert out.patterns_extracted == 0

    def test_frozen(self):
        out = PostJobOutput(
            operativo_id="op-1",
            patterns_extracted=1,
            archived=False,
        )
        with pytest.raises(AttributeError):
            out.archived = True
