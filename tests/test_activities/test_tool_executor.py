"""Tests for ToolExecutor with PolicyChain integration."""

import pytest

from agent_harness.activities.tool_executor import ToolExecutor
from agent_harness.core.permissions import ToolDeniedError


@pytest.fixture
def cpc_executor():
    """A ToolExecutor configured for the DCE domain with discover/execute tools."""
    return ToolExecutor(
        domain="dce",
        domain_tools=frozenset({"discover_api", "execute_api"}),
    )


class TestToolExecutorPermitted:
    def test_discover_api_permitted(self, cpc_executor):
        result = cpc_executor.check_permission("discover_api", agent="lamponne")
        assert result.permitted is True
        assert result.requires_sandbox is False

    def test_execute_api_permitted(self, cpc_executor):
        result = cpc_executor.check_permission("execute_api", agent="lamponne")
        assert result.permitted is True
        assert result.requires_sandbox is False


class TestToolExecutorDenied:
    def test_globally_denied_tool_raises(self, cpc_executor):
        with pytest.raises(ToolDeniedError):
            cpc_executor.check_permission("shell_exec", agent="lamponne")

    def test_unknown_tool_raises(self, cpc_executor):
        with pytest.raises(ToolDeniedError):
            cpc_executor.check_permission("unknown_tool", agent="lamponne")

    def test_filesystem_write_denied(self, cpc_executor):
        with pytest.raises(ToolDeniedError):
            cpc_executor.check_permission("filesystem_write", agent="lamponne")


class TestToolExecutorSandbox:
    def test_sandbox_tool_requires_sandbox(self, cpc_executor):
        result = cpc_executor.check_permission("run_python_sandbox", agent="lamponne")
        assert result.permitted is True
        assert result.requires_sandbox is True
