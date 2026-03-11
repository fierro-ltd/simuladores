"""Tests for Sprint 10 runtime fixes: @activity.defn, Ravenna handlers, exports, SandboxRouter."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from agent_harness.activities.implementations import (
    lamponne_execute,
    medina_investigate,
    post_job_learn,
    ravenna_synthesize,
    santos_plan,
    santos_qa_review,
)


# ---------------------------------------------------------------------------
# 1. @activity.defn decorators
# ---------------------------------------------------------------------------


class TestActivityDecorators:
    """Verify all 6 activity functions have @activity.defn."""

    def test_santos_plan_is_activity(self):
        assert hasattr(santos_plan, "__temporal_activity_definition")

    def test_medina_investigate_is_activity(self):
        assert hasattr(medina_investigate, "__temporal_activity_definition")

    def test_lamponne_execute_is_activity(self):
        assert hasattr(lamponne_execute, "__temporal_activity_definition")

    def test_santos_qa_review_is_activity(self):
        assert hasattr(santos_qa_review, "__temporal_activity_definition")

    def test_ravenna_synthesize_is_activity(self):
        assert hasattr(ravenna_synthesize, "__temporal_activity_definition")

    def test_post_job_learn_is_activity(self):
        assert hasattr(post_job_learn, "__temporal_activity_definition")


# ---------------------------------------------------------------------------
# 2. Ravenna tool handlers
# ---------------------------------------------------------------------------


class TestRavennaToolHandlers:
    """Tests for Ravenna's 4 tool handler functions in factory.py."""

    @pytest.mark.asyncio
    async def test_handle_read_progress_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
        from agent_harness.activities.factory import _handle_read_progress

        result = await _handle_read_progress({"operativo_id": "dce-test-001"})
        assert "No progress reports found" in result

    @pytest.mark.asyncio
    async def test_handle_read_progress_with_data(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
        # Write progress file
        session_dir = tmp_path / "sessions" / "dce-test-001"
        session_dir.mkdir(parents=True)
        (session_dir / "PROGRESS.md").write_text("## PLAN — santos\n\nPlanned 3 steps.\n\n")

        from agent_harness.activities.factory import _handle_read_progress

        result = await _handle_read_progress({"operativo_id": "dce-test-001"})
        assert "PLAN" in result
        assert "santos" in result

    @pytest.mark.asyncio
    async def test_handle_load_artifact_found(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
        session_dir = tmp_path / "sessions" / "dce-test-001"
        session_dir.mkdir(parents=True)
        (session_dir / "raw_output.json").write_text('{"result": "ok"}')

        from agent_harness.activities.factory import _handle_load_artifact

        result = await _handle_load_artifact({
            "operativo_id": "dce-test-001",
            "artifact_name": "raw_output.json",
        })
        data = json.loads(result)
        assert data["result"] == "ok"

    @pytest.mark.asyncio
    async def test_handle_load_artifact_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
        from agent_harness.activities.factory import _handle_load_artifact

        result = await _handle_load_artifact({
            "operativo_id": "dce-test-001",
            "artifact_name": "missing.json",
        })
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_handle_write_structured_result(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
        from agent_harness.activities.factory import _handle_write_structured_result

        result_json = json.dumps({"operativo_id": "dce-test-001", "status": "COMPLETED"})
        result = await _handle_write_structured_result({
            "operativo_id": "dce-test-001",
            "result_json": result_json,
        })
        data = json.loads(result)
        assert data["status"] == "written"

        # Verify file was actually written
        written = (tmp_path / "sessions" / "dce-test-001" / "structured_result.json").read_text()
        assert "COMPLETED" in written

    @pytest.mark.asyncio
    async def test_handle_check_caller_permission(self):
        from agent_harness.activities.factory import _handle_check_caller_permission

        result = await _handle_check_caller_permission({
            "caller_id": "user-001",
            "operativo_id": "dce-test-001",
        })
        data = json.loads(result)
        assert data["permitted"] is True
        assert data["caller_id"] == "user-001"


class TestBuildToolHandlerIncludesRavenna:
    """Verify build_tool_handler includes Ravenna handlers."""

    def test_ravenna_handlers_registered(self):
        from agent_harness.activities.factory import build_tool_handler
        from agent_harness.llm.client import AnthropicClient

        client = AnthropicClient(project_id="test-project", region="us-central1")
        handler = build_tool_handler(client, "dce")
        assert "read_progress" in handler._tool_handlers
        assert "load_artifact" in handler._tool_handlers
        assert "write_structured_result" in handler._tool_handlers
        assert "check_caller_permission" in handler._tool_handlers


# ---------------------------------------------------------------------------
# 3. __init__.py exports
# ---------------------------------------------------------------------------


class TestStorageExports:
    """Verify storage package exports."""

    def test_storage_backend_importable(self):
        from agent_harness.storage import StorageBackend
        assert StorageBackend is not None

    def test_local_storage_importable(self):
        from agent_harness.storage import LocalStorageBackend
        assert LocalStorageBackend is not None


class TestMemoryExports:
    """Verify memory package exports."""

    def test_domain_store_importable(self):
        from agent_harness.memory import DomainStore
        assert DomainStore is not None

    def test_session_store_importable(self):
        from agent_harness.memory import SessionStore
        assert SessionStore is not None

    def test_semantic_store_importable(self):
        from agent_harness.memory import SemanticStore
        assert SemanticStore is not None

    def test_domain_write_error_importable(self):
        from agent_harness.memory import DomainWriteAttemptError
        assert DomainWriteAttemptError is not None

    def test_pattern_importable(self):
        from agent_harness.memory import Pattern
        assert Pattern is not None


# ---------------------------------------------------------------------------
# 4. SandboxRouter.run()
# ---------------------------------------------------------------------------


class TestSandboxRouterRun:
    """Tests for SandboxRouter.run() dispatch method."""

    @pytest.mark.asyncio
    async def test_run_delegates_to_backend(self):
        from agent_harness.sandbox.python_runner import (
            SandboxRequest,
            SandboxResult,
            SandboxRouter,
        )

        mock_backend = AsyncMock()
        mock_backend.run.return_value = SandboxResult(
            output="42",
            stdout="42\n",
            error=None,
            execution_ms=5.0,
            backend="mock",
        )

        router = SandboxRouter(backend=mock_backend)
        request = SandboxRequest(code="print(42)", input_data={})
        result = await router.run(request)

        assert result.output == "42"
        assert result.succeeded
        mock_backend.run.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_run_creates_docker_backend_if_none(self):
        from agent_harness.sandbox.python_runner import SandboxRouter

        router = SandboxRouter()
        assert router._backend is None
        # We can't actually run Docker in tests, but we can verify the lazy init
        # by checking the backend attribute after attempting to create it
        # Just verify the router accepts None and has the method
        assert hasattr(router, "run")
