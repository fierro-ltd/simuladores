"""Google Cloud Storage backend."""

from __future__ import annotations

import asyncio
import re
from functools import partial
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.cloud.storage import Client


class GCSStorageBackend:
    """Storage backend using Google Cloud Storage.

    All GCS SDK calls are offloaded to a thread executor since the
    ``google-cloud-storage`` library is synchronous.
    """

    def __init__(self, bucket_name: str) -> None:
        self._bucket_name = bucket_name
        self._client: Client | None = None

    def _get_client(self) -> Client:
        """Lazy-initialise the GCS client."""
        if self._client is None:
            try:
                from google.cloud.storage import Client
            except ImportError as exc:
                raise ImportError(
                    "google-cloud-storage is required for GCSStorageBackend. "
                    "Install it with: pip install google-cloud-storage"
                ) from exc
            self._client = Client()
        return self._client

    # ------------------------------------------------------------------
    # Key sanitisation
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_key(key: str) -> str:
        """Remove path traversal components and leading slashes.

        * Strips leading ``/`` characters.
        * Removes any ``..`` path segments.
        * Collapses consecutive ``/`` into one.
        """
        # Strip leading slashes
        key = key.lstrip("/")
        # Remove ".." segments
        parts = key.split("/")
        parts = [p for p in parts if p != ".."]
        # Rejoin and collapse any consecutive slashes
        sanitized = "/".join(parts)
        sanitized = re.sub(r"/+", "/", sanitized)
        return sanitized

    # ------------------------------------------------------------------
    # StorageBackend interface
    # ------------------------------------------------------------------

    async def read(self, key: str) -> bytes:
        """Download a blob. Raises ``FileNotFoundError`` if missing."""
        from google.api_core.exceptions import NotFound

        safe_key = self._sanitize_key(key)
        loop = asyncio.get_running_loop()

        def _download() -> bytes:
            client = self._get_client()
            bucket = client.bucket(self._bucket_name)
            blob = bucket.blob(safe_key)
            try:
                return blob.download_as_bytes()
            except NotFound:
                raise FileNotFoundError(f"Storage key not found: {key}")

        return await loop.run_in_executor(None, _download)

    async def write(self, key: str, data: bytes) -> None:
        """Upload a blob."""
        safe_key = self._sanitize_key(key)
        loop = asyncio.get_running_loop()

        def _upload() -> None:
            client = self._get_client()
            bucket = client.bucket(self._bucket_name)
            blob = bucket.blob(safe_key)
            blob.upload_from_string(data)

        await loop.run_in_executor(None, _upload)

    async def exists(self, key: str) -> bool:
        """Check whether a blob exists."""
        safe_key = self._sanitize_key(key)
        loop = asyncio.get_running_loop()

        def _exists() -> bool:
            client = self._get_client()
            bucket = client.bucket(self._bucket_name)
            blob = bucket.blob(safe_key)
            return blob.exists()

        return await loop.run_in_executor(None, _exists)

    async def list(self, prefix: str) -> list[str]:
        """List all blob names under *prefix*."""
        safe_prefix = self._sanitize_key(prefix)
        loop = asyncio.get_running_loop()

        def _list() -> list[str]:
            client = self._get_client()
            bucket = client.bucket(self._bucket_name)
            blobs = bucket.list_blobs(prefix=safe_prefix)
            return [b.name for b in blobs]

        return await loop.run_in_executor(None, _list)
