"""IDP domain MCP server — exposes IDP tools via FastMCP."""
from __future__ import annotations

from fastmcp import FastMCP

from agent_harness.domains.idp.tools import (
    discover_api,
    get_operation_schema,
    list_operations,
)

mcp = FastMCP("idp-tools")


@mcp.tool()
def discover_idp_api(category: str | None = None) -> str:
    """Discover available IDP API operations, optionally filtered by category.
    Categories: jobs, plugins, settings."""
    return discover_api(category)


@mcp.tool()
def get_idp_operation_schema(operation: str) -> dict | None:
    """Get the schema for a specific IDP operation by name."""
    return get_operation_schema(operation)


@mcp.tool()
def list_idp_operations() -> list[str]:
    """List all 12 IDP operation names."""
    return list_operations()


if __name__ == "__main__":
    mcp.run()
