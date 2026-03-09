"""Structured logging for operativo activities.

Provides a lightweight structured logger that outputs JSON-formatted
log entries with operativo_id correlation. No external dependencies.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True)
class LogEntry:
    """A single structured log entry."""
    level: LogLevel
    message: str
    operativo_id: str = ""
    agent: str = ""
    phase: int = -1
    timestamp: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        data = {
            "level": self.level,
            "message": self.message,
            "ts": self.timestamp or time.time(),
        }
        if self.operativo_id:
            data["operativo_id"] = self.operativo_id
        if self.agent:
            data["agent"] = self.agent
        if self.phase >= 0:
            data["phase"] = self.phase
        if self.extra:
            data.update(self.extra)
        return json.dumps(data)


class OperativoLogger:
    """Structured logger bound to an operativo context.

    Usage:
        logger = OperativoLogger(operativo_id="op-123", agent="santos")
        logger.info("Plan generated", phase=1, extra={"steps": 5})
    """

    def __init__(self, operativo_id: str = "", agent: str = "") -> None:
        self.operativo_id = operativo_id
        self.agent = agent
        self._entries: list[LogEntry] = []

    def _log(
        self, level: LogLevel, message: str, phase: int = -1,
        extra: dict[str, Any] | None = None,
    ) -> LogEntry:
        entry = LogEntry(
            level=level,
            message=message,
            operativo_id=self.operativo_id,
            agent=self.agent,
            phase=phase,
            timestamp=time.time(),
            extra=extra or {},
        )
        self._entries.append(entry)
        return entry

    def debug(self, message: str, **kwargs: Any) -> LogEntry:
        return self._log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> LogEntry:
        return self._log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> LogEntry:
        return self._log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> LogEntry:
        return self._log(LogLevel.ERROR, message, **kwargs)

    @property
    def entries(self) -> list[LogEntry]:
        return list(self._entries)
