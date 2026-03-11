"""Tests for MCPExecutor."""
from __future__ import annotations

import importlib

import pytest
from fastmcp import FastMCP

# Import directly from the module to avoid agent_harness.agents.__init__
# which pulls in mem0 and other heavy dependencies.
_mod = importlib.import_module("agent_harness.agents.mcp_executor")
MCPExecutor = _mod.MCPExecutor

# Create a tiny test server
_test_mcp = FastMCP("test-echo")


@_test_mcp.tool()
def echo(message: str) -> str:
    """Echo a message back."""
    return message


@pytest.mark.anyio
async def test_mcp_executor_lists_tools():
    executor = MCPExecutor(_test_mcp, domain="test")
    tools = await executor.list_tools()
    names = [t.name for t in tools]
    assert "echo" in names


@pytest.mark.anyio
async def test_mcp_executor_calls_tool():
    executor = MCPExecutor(_test_mcp, domain="test")
    result = await executor.call_tool("echo", {"message": "hello"})
    assert len(result.content) > 0
    assert result.content[0].text == "hello"


def test_mcp_executor_domain():
    executor = MCPExecutor(_test_mcp, domain="test")
    assert executor.domain == "test"
