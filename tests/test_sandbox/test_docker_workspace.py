"""Tests for workspace integration in DockerSandboxBackend."""

import os
import tempfile

import pytest

from agent_harness.sandbox.docker_backend import _build_docker_args
from agent_harness.sandbox.python_runner import SandboxRequest


class TestBuildDockerArgsWithoutOperativo:
    def test_no_workspace_mounts(self):
        req = SandboxRequest(code="x = 1", input_data={})
        args = _build_docker_args(req)
        # No -v mounts should be present
        assert "-v" not in " ".join(args) or all("/sandbox/" not in a for a in args)

    def test_contains_base_flags(self):
        req = SandboxRequest(code="x = 1", input_data={})
        args = _build_docker_args(req)
        assert "--network=none" in args
        assert "--memory=128m" in args
        assert "--read-only" in args
        assert "--rm" in args

    def test_contains_image_and_command(self):
        req = SandboxRequest(code="x = 1", input_data={})
        args = _build_docker_args(req)
        assert "python:3.11-slim" in args
        assert "python" in args


class TestBuildDockerArgsWithOperativo:
    def test_workspace_mounts_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            req = SandboxRequest(
                code="x = 1", input_data={}, operativo_id="op-test"
            )
            args = _build_docker_args(req, sandbox_root=tmpdir)
            joined = " ".join(args)
            assert "/sandbox/input:ro" in joined
            assert "/sandbox/workspace:rw" in joined
            assert "/sandbox/output:rw" in joined

    def test_workspace_directories_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            req = SandboxRequest(
                code="x = 1", input_data={}, operativo_id="op-dirs"
            )
            _build_docker_args(req, sandbox_root=tmpdir)
            base = os.path.join(tmpdir, "op-dirs")
            assert os.path.isdir(os.path.join(base, "input"))
            assert os.path.isdir(os.path.join(base, "workspace"))
            assert os.path.isdir(os.path.join(base, "output"))

    def test_still_has_base_flags(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            req = SandboxRequest(
                code="x = 1", input_data={}, operativo_id="op-flags"
            )
            args = _build_docker_args(req, sandbox_root=tmpdir)
            assert "--network=none" in args
            assert "--memory=128m" in args
            assert "--read-only" in args

    def test_no_operativo_id_no_workspace_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            req = SandboxRequest(code="x = 1", input_data={})
            _build_docker_args(req, sandbox_root=tmpdir)
            # No subdirectories should be created
            assert os.listdir(tmpdir) == []
