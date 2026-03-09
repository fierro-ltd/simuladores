"""Tool executor: wraps PolicyChain for permission checks."""

from __future__ import annotations

from agent_harness.core.permissions import PolicyChain, PolicyResult


class ToolExecutor:
    """Wraps a PolicyChain for a specific domain and its allowed tools.

    Delegates permission checks to the underlying PolicyChain, which enforces
    the global deny list, domain allowlist, and sandbox routing.
    """

    def __init__(self, domain: str, domain_tools: frozenset[str]) -> None:
        self._chain = PolicyChain(domain=domain, domain_tools=domain_tools)

    def check_permission(self, tool_name: str, agent: str) -> PolicyResult:
        """Check whether a tool is permitted for the given agent.

        Raises ToolDeniedError for globally denied or non-allowlisted tools.
        Returns PolicyResult with requires_sandbox=True for sandbox tools.
        """
        return self._chain.check(tool_name, agent)
