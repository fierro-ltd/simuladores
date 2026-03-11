"""Tests for tool schema pinning (rug pull prevention)."""

import pytest
from fastmcp import FastMCP, Client

from agent_harness.core.tool_schema_registry import SchemaChangeEvent, ToolSchemaRegistry


def _make_server() -> FastMCP:
    """Create a test MCP server with known tools."""
    mcp = FastMCP("test-server")

    @mcp.tool()
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    @mcp.tool()
    def greet(name: str) -> str:
        """Greet someone."""
        return f"Hello, {name}"

    return mcp


@pytest.mark.asyncio
async def test_snapshot_and_verify_no_changes():
    """Snapshot a server, verify immediately — no changes expected."""
    mcp = _make_server()
    registry = ToolSchemaRegistry()

    async with Client(mcp) as client:
        await registry.snapshot(client)
        changes = await registry.verify(client)

    assert changes == []


@pytest.mark.asyncio
async def test_detects_schema_change():
    """Snapshot one server, verify against a modified server — change detected."""
    original = _make_server()
    registry = ToolSchemaRegistry()

    async with Client(original) as client:
        await registry.snapshot(client)

    # Create a modified server where 'add' has a different schema
    modified = FastMCP("test-server-modified")

    @modified.tool()
    def add(a: int, b: int, c: int = 0) -> int:
        """Add numbers with optional third param."""
        return a + b + c

    @modified.tool()
    def greet(name: str) -> str:
        """Greet someone."""
        return f"Hello, {name}"

    async with Client(modified) as client:
        changes = await registry.verify(client)

    assert len(changes) == 1
    assert changes[0].tool_name == "add"
    assert changes[0].original_hash != ""
    assert changes[0].current_hash != ""
    assert changes[0].original_hash != changes[0].current_hash


@pytest.mark.asyncio
async def test_detects_new_tool():
    """A new tool appearing after snapshot is flagged."""
    original = _make_server()
    registry = ToolSchemaRegistry()

    async with Client(original) as client:
        await registry.snapshot(client)

    # Create server with an extra tool
    expanded = _make_server()

    @expanded.tool()
    def secret_tool(payload: str) -> str:
        """Suspicious new tool."""
        return payload

    async with Client(expanded) as client:
        changes = await registry.verify(client)

    new_tools = [c for c in changes if c.original_hash == ""]
    assert len(new_tools) == 1
    assert new_tools[0].tool_name == "secret_tool"
