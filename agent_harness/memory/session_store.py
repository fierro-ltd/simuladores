"""Session memory store: per-operativo plan and progress tracking."""

from __future__ import annotations

from agent_harness.core.plan import PhaseResult
from agent_harness.storage.backend import StorageBackend


class SessionStore:
    """Read-write store for session-scoped operativo data.

    Files live under sessions/{operativo_id}/:
    - PLAN.md: execution plan (JSON)
    - PROGRESS.md: appended field reports from each phase
    """

    def __init__(self, backend: StorageBackend, operativo_id: str) -> None:
        self._backend = backend
        self._operativo_id = operativo_id

    def _key(self, filename: str) -> str:
        return f"sessions/{self._operativo_id}/{filename}"

    async def save_plan(self, plan_json: str) -> None:
        """Write the execution plan."""
        await self._backend.write(self._key("PLAN.md"), plan_json.encode("utf-8"))

    async def read_plan(self) -> str:
        """Read the execution plan. Raises FileNotFoundError if missing."""
        data = await self._backend.read(self._key("PLAN.md"))
        return data.decode("utf-8")

    async def append_progress(self, result: PhaseResult) -> None:
        """Append a phase field report to PROGRESS.md."""
        header = f"## {result.phase.name} — {result.agent}\n\n"
        entry = header + result.field_report + "\n\n"

        key = self._key("PROGRESS.md")
        if await self._backend.exists(key):
            existing = await self._backend.read(key)
            new_content = existing + entry.encode("utf-8")
        else:
            new_content = entry.encode("utf-8")

        await self._backend.write(key, new_content)

    async def read_progress(self) -> str:
        """Read progress file. Returns empty string if not exists."""
        key = self._key("PROGRESS.md")
        if not await self._backend.exists(key):
            return ""
        data = await self._backend.read(key)
        return data.decode("utf-8")
