"""Permission system: policy chain, deny lists, sandbox routing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

GLOBAL_DENY_LIST: frozenset[str] = frozenset({
    "shell_exec",
    "http_request",
    "filesystem_write",
    "os_exec",
    "subprocess",
})

SANDBOX_TOOLS: frozenset[str] = frozenset({
    "run_python_sandbox",
})


class PermissionLevel(StrEnum):
    """Permission level required for a tool."""

    AUTO = "AUTO"
    SESSION = "SESSION"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"


class ToolDeniedError(Exception):
    """Raised when a tool is denied by the policy chain."""


@dataclass(frozen=True)
class PolicyResult:
    """Result of a policy chain check."""

    permitted: bool
    requires_sandbox: bool = False
    requires_human_approval: bool = False


@dataclass(frozen=True)
class ToolPolicy:
    """Policy for a specific tool."""

    name: str
    permission: PermissionLevel


class PolicyChain:
    """Checks tool permissions through a chain of rules.

    Steps:
    1. Global deny list -> ToolDeniedError
    2. Domain allowlist -> ToolDeniedError if not in list
    3. Sandbox tools -> requires_sandbox=True
    """

    def __init__(self, domain: str, domain_tools: frozenset[str]) -> None:
        self._domain = domain
        self._domain_tools = domain_tools

    def check(self, tool_name: str, agent: str) -> PolicyResult:
        """Check whether a tool is permitted for the given agent."""
        # Step 1: Global deny list
        if tool_name in GLOBAL_DENY_LIST:
            raise ToolDeniedError(
                f"Tool '{tool_name}' is globally denied (agent={agent}, domain={self._domain})"
            )

        # Step 2: Domain allowlist
        if tool_name not in self._domain_tools and tool_name not in SANDBOX_TOOLS:
            raise ToolDeniedError(
                f"Tool '{tool_name}' is not in domain allowlist for '{self._domain}' "
                f"(agent={agent})"
            )

        # Step 3: Sandbox tools
        if tool_name in SANDBOX_TOOLS:
            return PolicyResult(permitted=True, requires_sandbox=True)

        return PolicyResult(permitted=True)
