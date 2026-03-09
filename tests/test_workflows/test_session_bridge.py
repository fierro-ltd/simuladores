"""Tests for session bridge workflow types."""

import pytest

from agent_harness.workflows.session_bridge import (
    PreserveMarker,
    SessionBridgeInput,
    SessionBridgeOutput,
    build_preserve_markers,
)


class TestPreserveMarker:
    def test_creation(self):
        marker = PreserveMarker(
            field_name="input_snapshot",
            content='{"fields": {}}',
            reason="QA comparison",
        )
        assert marker.field_name == "input_snapshot"
        assert marker.reason == "QA comparison"

    def test_frozen(self):
        marker = PreserveMarker(field_name="x", content="y", reason="z")
        with pytest.raises(AttributeError):
            marker.field_name = "changed"


class TestSessionBridgeInput:
    def test_creation(self):
        inp = SessionBridgeInput(operativo_id="op-123")
        assert inp.operativo_id == "op-123"
        assert inp.messages == []
        assert inp.preserve_markers == []
        assert inp.system_prompt == ""

    def test_with_markers(self):
        marker = PreserveMarker("field", "content", "reason")
        inp = SessionBridgeInput(
            operativo_id="op-1",
            messages=[{"role": "user", "content": "hi"}],
            preserve_markers=[marker],
            system_prompt="system",
        )
        assert len(inp.preserve_markers) == 1
        assert inp.preserve_markers[0].field_name == "field"

    def test_frozen(self):
        inp = SessionBridgeInput(operativo_id="op-1")
        with pytest.raises(AttributeError):
            inp.operativo_id = "changed"


class TestSessionBridgeOutput:
    def test_creation(self):
        out = SessionBridgeOutput(operativo_id="op-123")
        assert out.operativo_id == "op-123"
        assert out.compacted_messages == []
        assert out.preserved_content == []
        assert out.tokens_saved == 0

    def test_with_savings(self):
        out = SessionBridgeOutput(
            operativo_id="op-1",
            compacted_messages=[{"role": "user", "content": "summary"}],
            tokens_saved=5000,
        )
        assert out.tokens_saved == 5000
        assert len(out.compacted_messages) == 1

    def test_frozen(self):
        out = SessionBridgeOutput(operativo_id="op-1")
        with pytest.raises(AttributeError):
            out.tokens_saved = 999


class TestBuildPreserveMarkers:
    def test_empty(self):
        markers = build_preserve_markers({})
        assert markers == []

    def test_single_field(self):
        markers = build_preserve_markers(
            {"input_snapshot": '{"data": "value"}'}
        )
        assert len(markers) == 1
        assert markers[0].field_name == "input_snapshot"
        assert markers[0].reason == "critical context"

    def test_multiple_fields(self):
        markers = build_preserve_markers(
            {"field_a": "content_a", "field_b": "content_b"},
            reason="QA phase",
        )
        assert len(markers) == 2
        names = {m.field_name for m in markers}
        assert names == {"field_a", "field_b"}
        assert all(m.reason == "QA phase" for m in markers)
