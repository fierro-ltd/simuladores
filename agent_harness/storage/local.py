"""Local filesystem storage backend."""

from __future__ import annotations

from pathlib import Path


class LocalStorageBackend:
    """Storage backend using local filesystem."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()

    @property
    def base_path(self) -> str:
        """Return the resolved base path as a string."""
        return str(self._root)

    def _resolve_path(self, key: str) -> str:
        """Resolve a storage key to an absolute path within base_path.

        Always resolves the path and ensures it stays within the root
        directory, preventing path traversal attacks.
        """
        resolved = (self._root / key).resolve()
        # Ensure the resolved path is within the root
        if not str(resolved).startswith(str(self._root)):
            # Clamp to root — return root itself for traversal attempts
            return str(self._root / Path(key).name)
        return str(resolved)

    async def read(self, key: str) -> bytes:
        """Read bytes from a file. Raises FileNotFoundError if missing."""
        path = Path(self._resolve_path(key))
        if not path.is_file():
            raise FileNotFoundError(f"Storage key not found: {key}")
        return path.read_bytes()

    async def write(self, key: str, data: bytes) -> None:
        """Write bytes to a file, creating parent directories as needed."""
        path = Path(self._resolve_path(key))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def exists(self, key: str) -> bool:
        """Check if a key exists as a file."""
        path = Path(self._resolve_path(key))
        return path.is_file()

    async def list(self, prefix: str) -> list[str]:
        """List all keys under a prefix directory."""
        prefix_path = self._root / prefix
        if not prefix_path.exists():
            return []
        return [
            str(p.relative_to(self._root))
            for p in prefix_path.rglob("*")
            if p.is_file()
        ]
