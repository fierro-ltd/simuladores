"""Sandbox interface and routing.

Stable interface across Docker v1 and Monty v2 backends.
The backend can be swapped transparently — no agent code changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class SandboxRequest:
    """Request to execute Python code in an isolated sandbox."""

    code: str
    input_data: dict
    timeout_seconds: int = 10
    allowed_imports: list[str] = field(
        default_factory=lambda: ["re", "json", "string", "unicodedata", "datetime", "math"]
    )
    requires_json: bool = False
    operativo_id: str | None = None


@dataclass(frozen=True)
class SandboxResult:
    """Result from sandbox execution."""

    output: str
    stdout: str
    error: str | None
    execution_ms: float
    backend: str

    @property
    def succeeded(self) -> bool:
        return self.error is None


class SandboxBackend(Protocol):
    """Protocol for sandbox backends (Docker v1, Monty v2)."""

    async def run(self, request: SandboxRequest) -> SandboxResult: ...

    @property
    def name(self) -> str: ...


class SandboxRouter:
    """Routes sandbox requests to the appropriate backend.

    Currently: Docker only.
    Future: Monty for requests that don't require json (when Monty supports it).
    """

    def __init__(self, backend: SandboxBackend | None = None) -> None:
        self._monty_available = False
        self._backend = backend

    @property
    def active_backend(self) -> str:
        return "docker"

    @property
    def monty_available(self) -> bool:
        return self._monty_available

    async def run(self, request: SandboxRequest) -> SandboxResult:
        """Route a sandbox request to the active backend.

        Raises:
            RuntimeError: If no backend is configured.
        """
        if self._backend is None:
            from agent_harness.sandbox.docker_backend import DockerSandboxBackend

            self._backend = DockerSandboxBackend()
        return await self._backend.run(request)
