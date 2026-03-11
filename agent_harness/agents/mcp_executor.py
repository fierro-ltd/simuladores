"""MCP-based tool executor for Lamponne."""
from __future__ import annotations

from typing import Any

from fastmcp import Client, FastMCP


class MCPExecutor:
    """Executes tools via MCP client connection."""

    def __init__(self, mcp_server: FastMCP, domain: str) -> None:
        self._server = mcp_server
        self._domain = domain

    @property
    def domain(self) -> str:
        return self._domain

    async def list_tools(self) -> list:
        async with Client(self._server) as client:
            return await client.list_tools()

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        async with Client(self._server) as client:
            return await client.call_tool(tool_name, arguments)
