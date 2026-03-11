"""Audit logging for security-relevant gateway events.

Provides an in-memory audit log with structured entries.  Each entry
captures caller, domain, path, method, and a machine-readable event type.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class AuditEvent(StrEnum):
    """Machine-readable audit event types."""

    REQUEST = "REQUEST"
    AUTH_FAILURE = "AUTH_FAILURE"
    RATE_LIMITED = "RATE_LIMITED"
    DISPATCH = "DISPATCH"
    INJECTION_DETECTED = "INJECTION_DETECTED"


@dataclass(frozen=True)
class AuditEntry:
    """A single audit log entry."""

    event: AuditEvent
    caller_id: str = ""
    domain: str = ""
    operativo_id: str = ""
    path: str = ""
    method: str = ""
    status_code: int = 0
    request_id: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "event": str(self.event),
            "caller_id": self.caller_id,
            "domain": self.domain,
            "operativo_id": self.operativo_id,
            "path": self.path,
            "method": self.method,
            "status_code": self.status_code,
            "request_id": self.request_id,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict())


class AuditLogger:
    """In-memory audit logger with per-caller indexing.

    Parameters
    ----------
    max_entries:
        Maximum number of entries to retain.  Oldest entries are
        discarded when the cap is exceeded.
    """

    def __init__(self, max_entries: int = 10_000) -> None:
        self._max = max_entries
        self._entries: list[AuditEntry] = []
        self._by_caller: dict[str, list[AuditEntry]] = defaultdict(list)

    def log(self, entry: AuditEntry) -> None:
        """Record an audit entry."""
        # Inject timestamp if missing
        if entry.timestamp == 0.0:
            entry = AuditEntry(
                event=entry.event,
                caller_id=entry.caller_id,
                domain=entry.domain,
                operativo_id=entry.operativo_id,
                path=entry.path,
                method=entry.method,
                status_code=entry.status_code,
                request_id=entry.request_id,
                timestamp=time.time(),
            )

        self._entries.append(entry)
        if entry.caller_id:
            self._by_caller[entry.caller_id].append(entry)

        # Enforce cap
        if len(self._entries) > self._max:
            overflow = len(self._entries) - self._max
            removed = self._entries[:overflow]
            self._entries = self._entries[overflow:]
            # Clean up per-caller index
            for r in removed:
                if r.caller_id and r.caller_id in self._by_caller:
                    caller_list = self._by_caller[r.caller_id]
                    if caller_list and caller_list[0] is r:
                        caller_list.pop(0)

    @property
    def entries(self) -> list[AuditEntry]:
        """Return a copy of all audit entries."""
        return list(self._entries)

    def entries_by_caller(self, caller_id: str) -> list[AuditEntry]:
        """Return entries for a specific caller."""
        return list(self._by_caller.get(caller_id, []))
