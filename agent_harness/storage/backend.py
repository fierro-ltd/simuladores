"""Storage backend protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """Async storage backend for reading and writing bytes."""

    async def read(self, key: str) -> bytes:
        """Read bytes from storage. Raises FileNotFoundError if missing."""
        ...

    async def write(self, key: str, data: bytes) -> None:
        """Write bytes to storage."""
        ...

    async def exists(self, key: str) -> bool:
        """Check if a key exists in storage."""
        ...

    async def list(self, prefix: str) -> list[str]:
        """List all keys under a prefix."""
        ...
