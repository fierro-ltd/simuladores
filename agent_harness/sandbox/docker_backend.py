"""Docker sandbox backend (v1).

Rootless container, isolated per-session. No network access.
Read-only input volume. Ephemeral — destroyed after execution.

Timeout: 10 seconds. Memory: 128MB. Startup: ~195ms.
"""

from __future__ import annotations

import asyncio
import json
import time

from agent_harness.sandbox.python_runner import SandboxRequest, SandboxResult
from agent_harness.sandbox.workspace import create_workspace


def _build_docker_args(
    request: SandboxRequest,
    sandbox_root: str = "/tmp/agent-sandbox",
) -> list[str]:
    """Build Docker CLI arguments for a sandbox run.

    When request.operativo_id is set, creates a workspace and adds
    volume mounts for input (ro), workspace (rw), and output (rw).
    """
    args = [
        "run", "--rm",
        "--network=none",
        "--memory=128m",
        "--read-only",
        "--tmpfs=/tmp:size=16m",
        f"--stop-timeout={request.timeout_seconds}",
    ]

    if request.operativo_id is not None:
        ws = create_workspace(request.operativo_id, root=sandbox_root)
        args.extend(ws.docker_mounts())

    args.extend([
        "python:3.11-slim",
        "python", "-c",
    ])

    return args


class DockerSandboxBackend:
    """Executes Python code in an isolated Docker container."""

    @property
    def name(self) -> str:
        return "docker"

    async def run(self, request: SandboxRequest) -> SandboxResult:
        """Run code in a Docker container.

        Container config:
        - Image: python:3.11-slim
        - Network: none
        - Memory: 128MB
        - Read-only filesystem (except /tmp)
        - Input data passed via stdin as JSON
        - When operativo_id set: workspace volumes mounted
        """
        start = time.monotonic()

        # Build the wrapper script that enforces import restrictions
        allowed = set(request.allowed_imports)
        wrapper = _build_wrapper(request.code, request.input_data, allowed)

        docker_args = _build_docker_args(request)

        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", *docker_args, wrapper,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=request.timeout_seconds + 5,  # grace period
            )
            elapsed = (time.monotonic() - start) * 1000

            if proc.returncode != 0:
                return SandboxResult(
                    output="",
                    stdout=stdout.decode(errors="replace"),
                    error=stderr.decode(errors="replace"),
                    execution_ms=elapsed,
                    backend="docker",
                )

            return SandboxResult(
                output=stdout.decode(errors="replace").strip(),
                stdout=stdout.decode(errors="replace"),
                error=None,
                execution_ms=elapsed,
                backend="docker",
            )

        except asyncio.TimeoutError:
            elapsed = (time.monotonic() - start) * 1000
            return SandboxResult(
                output="",
                stdout="",
                error=f"Execution timed out after {request.timeout_seconds}s",
                execution_ms=elapsed,
                backend="docker",
            )
        except FileNotFoundError:
            return SandboxResult(
                output="",
                stdout="",
                error="Docker not available",
                execution_ms=0.0,
                backend="docker",
            )


def _build_wrapper(code: str, input_data: dict, allowed_imports: set[str]) -> str:
    """Build a Python wrapper script that restricts imports and injects input."""
    input_json = json.dumps(input_data)
    return f"""
import sys
import importlib

_ALLOWED = {allowed_imports!r}
_original_import = __builtins__.__import__

def _restricted_import(name, *args, **kwargs):
    top_level = name.split('.')[0]
    if top_level not in _ALLOWED:
        raise ImportError(f"Import '{{name}}' is not allowed. Allowed: {{_ALLOWED}}")
    return _original_import(name, *args, **kwargs)

__builtins__.__import__ = _restricted_import

import json
input_data = json.loads('''{input_json}''')

{code}
"""
