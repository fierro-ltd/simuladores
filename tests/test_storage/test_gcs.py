"""Tests for GCS storage backend (fully mocked — no real GCS calls)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Skip entire module if google-cloud-storage is not installed.
gcs_storage = pytest.importorskip("google.cloud.storage")

from google.api_core.exceptions import NotFound  # noqa: E402

from agent_harness.storage.gcs import GCSStorageBackend  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client():
    """Return a MagicMock that stands in for ``google.cloud.storage.Client``."""
    return MagicMock()


@pytest.fixture
def backend(mock_client):
    """Return a GCSStorageBackend with the client pre-injected."""
    be = GCSStorageBackend(bucket_name="test-bucket")
    be._client = mock_client
    return be


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _blob(mock_client: MagicMock) -> MagicMock:
    """Shortcut to get the mock blob returned by ``bucket.blob(...)``."""
    return mock_client.bucket.return_value.blob.return_value


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGCSStorageBackend:
    async def test_write_uploads_blob(self, backend, mock_client):
        await backend.write("some/key.txt", b"payload")

        mock_client.bucket.assert_called_with("test-bucket")
        mock_client.bucket.return_value.blob.assert_called_with("some/key.txt")
        _blob(mock_client).upload_from_string.assert_called_once_with(b"payload")

    async def test_read_downloads_blob(self, backend, mock_client):
        _blob(mock_client).download_as_bytes.return_value = b"hello"

        result = await backend.read("some/key.txt")

        assert result == b"hello"
        mock_client.bucket.return_value.blob.assert_called_with("some/key.txt")
        _blob(mock_client).download_as_bytes.assert_called_once()

    async def test_read_missing_raises(self, backend, mock_client):
        _blob(mock_client).download_as_bytes.side_effect = NotFound("not found")

        with pytest.raises(FileNotFoundError, match="Storage key not found"):
            await backend.read("missing.txt")

    async def test_exists_true(self, backend, mock_client):
        _blob(mock_client).exists.return_value = True
        assert await backend.exists("present.txt") is True

    async def test_exists_false(self, backend, mock_client):
        _blob(mock_client).exists.return_value = False
        assert await backend.exists("absent.txt") is False

    async def test_list_keys(self, backend, mock_client):
        blob_a = MagicMock()
        blob_a.name = "prefix/a.txt"
        blob_b = MagicMock()
        blob_b.name = "prefix/b.txt"
        mock_client.bucket.return_value.list_blobs.return_value = [blob_a, blob_b]

        keys = await backend.list("prefix")

        mock_client.bucket.return_value.list_blobs.assert_called_with(prefix="prefix")
        assert keys == ["prefix/a.txt", "prefix/b.txt"]

    async def test_list_empty(self, backend, mock_client):
        mock_client.bucket.return_value.list_blobs.return_value = []

        keys = await backend.list("empty_prefix")
        assert keys == []

    async def test_path_traversal_blocked(self, backend, mock_client):
        """Ensure '..' segments are stripped from keys."""
        _blob(mock_client).download_as_bytes.return_value = b"safe"

        await backend.read("foo/../etc/passwd")

        # The blob key should have ".." removed
        mock_client.bucket.return_value.blob.assert_called_with("foo/etc/passwd")

    async def test_path_traversal_absolute(self, backend, mock_client):
        """Ensure leading '/' is stripped from keys."""
        _blob(mock_client).download_as_bytes.return_value = b"safe"

        await backend.read("/etc/passwd")

        mock_client.bucket.return_value.blob.assert_called_with("etc/passwd")

    async def test_lazy_client_initialisation(self):
        """Client is not created until first use."""
        be = GCSStorageBackend(bucket_name="lazy-bucket")
        assert be._client is None

    async def test_sanitize_key_double_dots_only(self):
        """A key consisting only of '..' segments resolves to empty string."""
        assert GCSStorageBackend._sanitize_key("../../..") == ""

    async def test_sanitize_key_mixed(self):
        assert GCSStorageBackend._sanitize_key("/a/../b/c") == "a/b/c"
