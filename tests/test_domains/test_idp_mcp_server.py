"""Tests for IDP MCP server."""
from __future__ import annotations

import pytest
from fastmcp import Client

from agent_harness.domains.idp.mcp_server import mcp


def test_idp_mcp_server_name():
    assert mcp.name == "idp-tools"


@pytest.mark.anyio
async def test_idp_mcp_server_lists_tools():
    async with Client(mcp) as client:
        tools = await client.list_tools()
    names = [t.name for t in tools]
    assert "discover_idp_api" in names
    assert "get_idp_operation_schema" in names
    assert "list_idp_operations" in names


@pytest.mark.anyio
async def test_idp_mcp_server_discover_api_tool():
    async with Client(mcp) as client:
        result = await client.call_tool("discover_idp_api", {})
    assert len(result.content) > 0
    assert result.content[0].text
    assert "jobs" in result.content[0].text
