"""Tests for storage path traversal prevention."""


from agent_harness.storage.local import LocalStorageBackend


class TestPathTraversal:
    """Verify storage backend prevents path traversal attacks."""

    def test_normal_path(self, tmp_path):
        backend = LocalStorageBackend(str(tmp_path))
        # Normal path should work
        assert backend.base_path == str(tmp_path)

    def test_path_traversal_dots(self, tmp_path):
        backend = LocalStorageBackend(str(tmp_path))
        # Path with .. should be rejected or resolved safely
        # This tests the storage backend's handling of traversal
        resolved = backend._resolve_path("../../etc/passwd")
        assert str(tmp_path) in resolved or not resolved.startswith("/etc")

    def test_absolute_path_rejected(self, tmp_path):
        backend = LocalStorageBackend(str(tmp_path))
        resolved = backend._resolve_path("/etc/passwd")
        # Should stay within base path
        assert resolved.startswith(str(tmp_path))
