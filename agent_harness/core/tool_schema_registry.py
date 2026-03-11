"""Tool schema pinning — rug pull prevention.

Snapshots SHA-256 hashes of MCP tool schemas at startup and verifies
them before each operativo. Detects schema changes that could indicate
a compromised or swapped tool server (rug pull attack).

Usage:
    registry = ToolSchemaRegistry()
    await registry.snapshot(client)   # at startup
    changes = await registry.verify(client)  # before each operativo
    if changes:
        raise SecurityError(...)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SchemaChangeEvent:
    """Records a detected schema change for a tool."""

    tool_name: str
    original_hash: str
    current_hash: str


class ToolSchemaRegistry:
    """Captures and verifies MCP tool schema fingerprints."""

    def __init__(self) -> None:
        self._snapshots: dict[str, str] = {}

    @staticmethod
    def _hash_schema(schema: dict) -> str:
        """Deterministic SHA-256 hash of a JSON-serializable schema."""
        canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    async def snapshot(self, client) -> None:
        """Capture current tool schemas as the trusted baseline.

        Args:
            client: An MCP client with a list_tools() method that
                    returns tools with .name and .inputSchema attributes.
        """
        tools = await client.list_tools()
        self._snapshots = {
            tool.name: self._hash_schema(tool.inputSchema)
            for tool in tools
        }

    async def verify(self, client) -> list[SchemaChangeEvent]:
        """Compare current tool schemas against the snapshot.

        Returns a list of SchemaChangeEvent for any tools whose schema
        has changed since the snapshot was taken.
        """
        tools = await client.list_tools()
        changes: list[SchemaChangeEvent] = []

        for tool in tools:
            current_hash = self._hash_schema(tool.inputSchema)
            original_hash = self._snapshots.get(tool.name)

            if original_hash is None:
                # New tool appeared — also suspicious
                changes.append(SchemaChangeEvent(
                    tool_name=tool.name,
                    original_hash="",
                    current_hash=current_hash,
                ))
            elif current_hash != original_hash:
                changes.append(SchemaChangeEvent(
                    tool_name=tool.name,
                    original_hash=original_hash,
                    current_hash=current_hash,
                ))

        return changes
