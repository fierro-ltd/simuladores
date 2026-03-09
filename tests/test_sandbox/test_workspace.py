"""Tests for per-operativo sandbox workspace."""

import os
import tempfile

import pytest

from agent_harness.sandbox.workspace import (
    OperativoWorkspace,
    cleanup_workspace,
    create_workspace,
)


class TestOperativoWorkspace:
    def test_paths(self):
        ws = OperativoWorkspace(operativo_id="op-123", root="/tmp/agent-sandbox")
        assert ws.base_path == "/tmp/agent-sandbox/op-123"
        assert ws.input_path == "/tmp/agent-sandbox/op-123/input"
        assert ws.workspace_path == "/tmp/agent-sandbox/op-123/workspace"
        assert ws.output_path == "/tmp/agent-sandbox/op-123/output"

    def test_frozen(self):
        ws = OperativoWorkspace(operativo_id="op-123", root="/tmp/agent-sandbox")
        with pytest.raises(AttributeError):
            ws.operativo_id = "changed"  # type: ignore[misc]

    def test_docker_mounts(self):
        ws = OperativoWorkspace(operativo_id="op-123", root="/tmp/agent-sandbox")
        mounts = ws.docker_mounts()
        assert len(mounts) == 3
        # input is read-only
        assert any("/tmp/agent-sandbox/op-123/input:/sandbox/input:ro" in m for m in mounts)
        # workspace is read-write
        assert any("/tmp/agent-sandbox/op-123/workspace:/sandbox/workspace:rw" in m for m in mounts)
        # output is read-write
        assert any("/tmp/agent-sandbox/op-123/output:/sandbox/output:rw" in m for m in mounts)

    def test_docker_mounts_format(self):
        """Each mount string should start with -v flag."""
        ws = OperativoWorkspace(operativo_id="op-456", root="/tmp/test-root")
        mounts = ws.docker_mounts()
        for m in mounts:
            assert m.startswith("-v"), f"Mount arg should start with -v: {m}"


class TestCreateWorkspace:
    def test_creates_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = create_workspace("op-abc", root=tmpdir)
            assert os.path.isdir(ws.input_path)
            assert os.path.isdir(ws.workspace_path)
            assert os.path.isdir(ws.output_path)

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws1 = create_workspace("op-abc", root=tmpdir)
            ws2 = create_workspace("op-abc", root=tmpdir)
            assert ws1 == ws2
            assert os.path.isdir(ws1.input_path)

    def test_different_operativo_ids(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws1 = create_workspace("op-1", root=tmpdir)
            ws2 = create_workspace("op-2", root=tmpdir)
            assert ws1.base_path != ws2.base_path


class TestCleanupWorkspace:
    def test_removes_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = create_workspace("op-cleanup", root=tmpdir)
            assert os.path.isdir(ws.base_path)
            cleanup_workspace(ws)
            assert not os.path.exists(ws.base_path)

    def test_safe_on_nonexistent(self):
        ws = OperativoWorkspace(operativo_id="nonexistent", root="/tmp/does-not-exist-xyz")
        # Should not raise
        cleanup_workspace(ws)
