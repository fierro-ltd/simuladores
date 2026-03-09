"""Tests for structured logging."""

import json
import pytest

from agent_harness.observability.logging import (
    LogLevel,
    LogEntry,
    OperativoLogger,
)


class TestLogEntry:
    def test_creation(self):
        entry = LogEntry(level=LogLevel.INFO, message="test")
        assert entry.level == LogLevel.INFO
        assert entry.message == "test"

    def test_to_json(self):
        entry = LogEntry(
            level=LogLevel.INFO, message="hello",
            operativo_id="op-1", agent="santos", phase=1,
        )
        data = json.loads(entry.to_json())
        assert data["level"] == "INFO"
        assert data["message"] == "hello"
        assert data["operativo_id"] == "op-1"
        assert data["agent"] == "santos"
        assert data["phase"] == 1

    def test_to_json_minimal(self):
        entry = LogEntry(level=LogLevel.DEBUG, message="x")
        data = json.loads(entry.to_json())
        assert "operativo_id" not in data
        assert "agent" not in data

    def test_to_json_with_extra(self):
        entry = LogEntry(
            level=LogLevel.INFO, message="done",
            extra={"steps": 5, "duration_ms": 100},
        )
        data = json.loads(entry.to_json())
        assert data["steps"] == 5
        assert data["duration_ms"] == 100

    def test_frozen(self):
        entry = LogEntry(level=LogLevel.INFO, message="x")
        with pytest.raises(AttributeError):
            entry.message = "changed"


class TestOperativoLogger:
    def test_creation(self):
        logger = OperativoLogger(operativo_id="op-1", agent="santos")
        assert logger.operativo_id == "op-1"
        assert logger.agent == "santos"

    def test_info(self):
        logger = OperativoLogger(operativo_id="op-1")
        entry = logger.info("Plan complete", phase=1)
        assert entry.level == LogLevel.INFO
        assert entry.operativo_id == "op-1"
        assert entry.phase == 1

    def test_debug(self):
        logger = OperativoLogger()
        entry = logger.debug("Tool call", extra={"tool": "extract"})
        assert entry.level == LogLevel.DEBUG
        assert entry.extra["tool"] == "extract"

    def test_warning(self):
        logger = OperativoLogger()
        entry = logger.warning("QA issue found")
        assert entry.level == LogLevel.WARNING

    def test_error(self):
        logger = OperativoLogger()
        entry = logger.error("Phase failed")
        assert entry.level == LogLevel.ERROR

    def test_entries_collected(self):
        logger = OperativoLogger(operativo_id="op-1")
        logger.info("a")
        logger.warning("b")
        logger.error("c")
        assert len(logger.entries) == 3
        assert logger.entries[0].message == "a"

    def test_entries_returns_copy(self):
        logger = OperativoLogger()
        logger.info("x")
        entries = logger.entries
        entries.clear()
        assert len(logger.entries) == 1
