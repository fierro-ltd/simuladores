"""Tests for DCE MCP server."""
from __future__ import annotations

import pytest
from fastmcp import Client

from agent_harness.domains.dce.mcp_server import mcp


def test_dce_mcp_server_name():
    assert mcp.name == "dce-tools"


@pytest.mark.anyio
async def test_dce_mcp_server_lists_tools():
    async with Client(mcp) as client:
        tools = await client.list_tools()
    names = [t.name for t in tools]
    assert "discover_dce_api" in names
    assert "get_dce_operation_schema" in names
    assert "list_dce_operations" in names


@pytest.mark.anyio
async def test_dce_mcp_server_discover_api_tool():
    async with Client(mcp) as client:
        result = await client.call_tool("discover_dce_api", {})
    assert len(result.content) > 0
    assert result.content[0].text
    assert "extraction" in result.content[0].text
