"""Per-operativo sandbox workspace.

Each operativo gets an isolated directory structure:
  <root>/<operativo_id>/
    input/      — read-only input files (mounted :ro in Docker)
    workspace/  — scratch space for execution (mounted :rw)
    output/     — results written by sandbox code (mounted :rw)
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class OperativoWorkspace:
    """Isolated directory workspace for a single operativo."""

    operativo_id: str
    root: str

    @property
    def base_path(self) -> str:
        return os.path.join(self.root, self.operativo_id)

    @property
    def input_path(self) -> str:
        return os.path.join(self.base_path, "input")

    @property
    def workspace_path(self) -> str:
        return os.path.join(self.base_path, "workspace")

    @property
    def output_path(self) -> str:
        return os.path.join(self.base_path, "output")

    def docker_mounts(self) -> list[str]:
        """Return Docker -v mount arguments for this workspace."""
        return [
            f"-v{self.input_path}:/sandbox/input:ro",
            f"-v{self.workspace_path}:/sandbox/workspace:rw",
            f"-v{self.output_path}:/sandbox/output:rw",
        ]


def create_workspace(
    operativo_id: str, root: str = "/tmp/agent-sandbox"
) -> OperativoWorkspace:
    """Create workspace directories for an operativo. Idempotent."""
    ws = OperativoWorkspace(operativo_id=operativo_id, root=root)
    os.makedirs(ws.input_path, exist_ok=True)
    os.makedirs(ws.workspace_path, exist_ok=True)
    os.makedirs(ws.output_path, exist_ok=True)
    return ws


def cleanup_workspace(workspace: OperativoWorkspace) -> None:
    """Remove workspace directories. Safe if nonexistent."""
    shutil.rmtree(workspace.base_path, ignore_errors=True)
