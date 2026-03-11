"""DCE domain MCP server — exposes DCE tools via FastMCP."""
from __future__ import annotations

from fastmcp import FastMCP

from agent_harness.domains.dce.tools import (
    discover_api,
    get_operation_schema,
    list_operations,
)

mcp = FastMCP("dce-tools")


@mcp.tool()
def discover_dce_api(category: str | None = None) -> str:
    """Discover available DCE API operations, optionally filtered by category.
    Categories: extraction, navigation, validation, tools, global."""
    return discover_api(category)


@mcp.tool()
def get_dce_operation_schema(operation: str) -> dict | None:
    """Get the schema for a specific DCE operation by name."""
    return get_operation_schema(operation)


@mcp.tool()
def list_dce_operations() -> list[str]:
    """List all 28 DCE operation names."""
    return list_operations()


if __name__ == "__main__":
    mcp.run()
