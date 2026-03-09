"""Tests for the audit logger."""

from __future__ import annotations

import json

import pytest

from agent_harness.observability.audit import AuditEntry, AuditEvent, AuditLogger


class TestAuditEvent:
    """AuditEvent enum tests."""

    def test_all_events_exist(self):
        expected = {"REQUEST", "AUTH_FAILURE", "RATE_LIMITED", "DISPATCH", "INJECTION_DETECTED"}
        assert {e.value for e in AuditEvent} == expected

    def test_str_enum(self):
        assert str(AuditEvent.REQUEST) == "REQUEST"


class TestAuditEntry:
    """AuditEntry dataclass tests."""

    def test_to_dict(self):
        entry = AuditEntry(
            event=AuditEvent.REQUEST,
            caller_id="acme",
            path="/health",
            method="GET",
            status_code=200,
            request_id="r-1",
            timestamp=1000.0,
        )
        d = entry.to_dict()
        assert d["event"] == "REQUEST"
        assert d["caller_id"] == "acme"
        assert d["status_code"] == 200

    def test_to_json(self):
        entry = AuditEntry(event=AuditEvent.DISPATCH, timestamp=1.0)
        parsed = json.loads(entry.to_json())
        assert parsed["event"] == "DISPATCH"

    def test_frozen(self):
        entry = AuditEntry(event=AuditEvent.REQUEST)
        with pytest.raises(AttributeError):
            entry.event = AuditEvent.DISPATCH  # type: ignore[misc]


class TestAuditLogger:
    """AuditLogger tests."""

    def test_log_and_retrieve(self):
        logger = AuditLogger()
        entry = AuditEntry(event=AuditEvent.REQUEST, caller_id="c1", timestamp=1.0)
        logger.log(entry)
        assert len(logger.entries) == 1
        assert logger.entries[0].caller_id == "c1"

    def test_auto_timestamp(self):
        logger = AuditLogger()
        entry = AuditEntry(event=AuditEvent.REQUEST)
        logger.log(entry)
        assert logger.entries[0].timestamp > 0

    def test_entries_by_caller(self):
        logger = AuditLogger()
        logger.log(AuditEntry(event=AuditEvent.REQUEST, caller_id="c1", timestamp=1.0))
        logger.log(AuditEntry(event=AuditEvent.REQUEST, caller_id="c2", timestamp=2.0))
        logger.log(AuditEntry(event=AuditEvent.DISPATCH, caller_id="c1", timestamp=3.0))
        assert len(logger.entries_by_caller("c1")) == 2
        assert len(logger.entries_by_caller("c2")) == 1
        assert len(logger.entries_by_caller("c3")) == 0

    def test_max_entries_cap(self):
        logger = AuditLogger(max_entries=3)
        for i in range(5):
            logger.log(AuditEntry(
                event=AuditEvent.REQUEST,
                caller_id=f"c{i}",
                timestamp=float(i),
            ))
        assert len(logger.entries) == 3
        # Oldest entries (c0, c1) should be gone
        callers = [e.caller_id for e in logger.entries]
        assert callers == ["c2", "c3", "c4"]

    def test_entries_returns_copy(self):
        logger = AuditLogger()
        logger.log(AuditEntry(event=AuditEvent.REQUEST, timestamp=1.0))
        entries = logger.entries
        entries.clear()
        assert len(logger.entries) == 1
