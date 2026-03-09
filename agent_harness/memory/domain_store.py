"""Domain memory store: read-only access to domain knowledge files."""

from __future__ import annotations

import logging

from agent_harness.storage.backend import StorageBackend

logger = logging.getLogger(__name__)


class DomainWriteAttemptError(PermissionError):
    """Raised when an agent attempts to write to domain memory."""


class DomainStore:
    """Read-only store for domain knowledge files.

    Domain files live at domains/{domain}/{DOMAIN_UPPER}.md and are never
    written by agents at runtime (architecture invariant #4).
    """

    def __init__(self, backend: StorageBackend, domain: str) -> None:
        self._backend = backend
        self._domain = domain

    async def read(self) -> str:
        """Read the domain knowledge file. Returns string content."""
        key = f"domains/{self._domain}/{self._domain.upper()}.md"
        data = await self._backend.read(key)
        return data.decode("utf-8")

    async def write(self, content: str) -> None:
        """ALWAYS raises DomainWriteAttemptError. Domain files are read-only."""
        logger.critical(
            "Agent attempted to write domain memory for '%s'. This is forbidden.",
            self._domain,
        )
        raise DomainWriteAttemptError(
            f"Domain memory for '{self._domain}' is read-only at runtime. "
            "Domain files can only be updated via human-approved Temporal signal."
        )
