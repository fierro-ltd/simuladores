"""Tests for IDP tool handlers in activities/factory.py."""

from __future__ import annotations

import json

import pytest

from agent_harness.activities.factory import (
    _get_idp_client,
    _handle_idp_discover_api,
    _handle_idp_execute_api,
    _handle_idp_get_job_detail,
    _handle_idp_get_job_status,
    _handle_idp_list_jobs,
    _handle_idp_patch_job_verdict,
    _handle_idp_get_plugin,
    _handle_idp_update_schema,
    _handle_idp_calibrate_schema,
    _handle_idp_get_calibration_status,
    _handle_idp_upload_document,
    build_tool_handler,
)
from agent_harness.llm.client import AnthropicClient
from agent_harness.llm.tool_handler import ToolHandler


# ---------------------------------------------------------------------------
# _get_idp_client helper
# ---------------------------------------------------------------------------


class TestGetIdpClient:
    """Tests for _get_idp_client configuration helper."""

    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("IDP_PLATFORM_URL", raising=False)
        monkeypatch.delenv("IDP_PLATFORM_TOKEN", raising=False)
        base_url, headers = _get_idp_client()
        assert base_url == "http://localhost:8100"
        assert headers == {}

    def test_custom_url_and_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("IDP_PLATFORM_URL", "https://idp.example.com")
        monkeypatch.setenv("IDP_PLATFORM_TOKEN", "tok-abc")
        base_url, headers = _get_idp_client()
        assert base_url == "https://idp.example.com"
        assert headers == {"Authorization": "Bearer tok-abc"}


# ---------------------------------------------------------------------------
# discover_api / execute_api (no HTTP)
# ---------------------------------------------------------------------------


class TestIdpDiscoverApi:
    """Tests for _handle_idp_discover_api."""

    @pytest.mark.asyncio
    async def test_all_categories(self) -> None:
        result = await _handle_idp_discover_api({})
        assert "[jobs]" in result
        assert "[plugins]" in result
        assert "[settings]" in result

    @pytest.mark.asyncio
    async def test_filter_by_category(self) -> None:
        result = await _handle_idp_discover_api({"category": "jobs"})
        assert "[jobs]" in result
        assert "[plugins]" not in result

    @pytest.mark.asyncio
    async def test_unknown_category_returns_empty(self) -> None:
        result = await _handle_idp_discover_api({"category": "nonexistent"})
        assert result == ""


class TestIdpExecuteApi:
    """Tests for _handle_idp_execute_api."""

    @pytest.mark.asyncio
    async def test_known_operation(self) -> None:
        result = await _handle_idp_execute_api({
            "operation": "upload_document",
            "params": {"document_path": "/tmp/doc.pdf", "plugin_id": "invoices"},
        })
        data = json.loads(result)
        assert data["status"] == "executed"
        assert data["operation"] == "upload_document"
        assert data["schema"] is not None

    @pytest.mark.asyncio
    async def test_unknown_operation(self) -> None:
        result = await _handle_idp_execute_api({
            "operation": "nonexistent_op",
            "params": {},
        })
        data = json.loads(result)
        assert "error" in data
        assert "Unknown IDP operation" in data["error"]


# ---------------------------------------------------------------------------
# HTTP handler parameter validation (no actual HTTP calls)
# ---------------------------------------------------------------------------


class TestIdpUploadDocument:
    """Tests for _handle_idp_upload_document param validation."""

    @pytest.mark.asyncio
    async def test_missing_document_path(self) -> None:
        result = await _handle_idp_upload_document({"plugin_id": "invoices"})
        data = json.loads(result)
        assert "error" in data
        assert "document_path is required" in data["error"]

    @pytest.mark.asyncio
    async def test_file_not_found(self) -> None:
        result = await _handle_idp_upload_document({
            "document_path": "/nonexistent/file.pdf",
            "plugin_id": "invoices",
        })
        data = json.loads(result)
        assert "error" in data
        assert "File not found" in data["error"]

    @pytest.mark.asyncio
    async def test_missing_plugin_id(self, tmp_path) -> None:
        doc = tmp_path / "test.pdf"
        doc.write_bytes(b"%PDF-1.4 test")
        result = await _handle_idp_upload_document({
            "document_path": str(doc),
        })
        data = json.loads(result)
        assert "error" in data
        assert "plugin_id is required" in data["error"]


class TestIdpGetJobDetail:
    """Tests for _handle_idp_get_job_detail param validation."""

    @pytest.mark.asyncio
    async def test_missing_job_id(self) -> None:
        result = await _handle_idp_get_job_detail({})
        data = json.loads(result)
        assert "error" in data
        assert "job_id is required" in data["error"]


class TestIdpGetJobStatus:
    """Tests for _handle_idp_get_job_status param validation."""

    @pytest.mark.asyncio
    async def test_missing_job_id(self) -> None:
        result = await _handle_idp_get_job_status({})
        data = json.loads(result)
        assert "error" in data
        assert "job_id is required" in data["error"]


class TestIdpPatchJobVerdict:
    """Tests for _handle_idp_patch_job_verdict param validation."""

    @pytest.mark.asyncio
    async def test_missing_job_id(self) -> None:
        result = await _handle_idp_patch_job_verdict({"verdict": "approved"})
        data = json.loads(result)
        assert "error" in data
        assert "job_id is required" in data["error"]

    @pytest.mark.asyncio
    async def test_missing_verdict(self) -> None:
        result = await _handle_idp_patch_job_verdict({"job_id": "j-123"})
        data = json.loads(result)
        assert "error" in data
        assert "verdict is required" in data["error"]


class TestIdpGetPlugin:
    """Tests for _handle_idp_get_plugin param validation."""

    @pytest.mark.asyncio
    async def test_missing_plugin_id(self) -> None:
        result = await _handle_idp_get_plugin({})
        data = json.loads(result)
        assert "error" in data
        assert "plugin_id is required" in data["error"]


class TestIdpUpdateSchema:
    """Tests for _handle_idp_update_schema param validation."""

    @pytest.mark.asyncio
    async def test_missing_plugin_id(self) -> None:
        result = await _handle_idp_update_schema({"schema": {"fields": []}})
        data = json.loads(result)
        assert "error" in data
        assert "plugin_id is required" in data["error"]

    @pytest.mark.asyncio
    async def test_missing_schema(self) -> None:
        result = await _handle_idp_update_schema({"plugin_id": "invoices"})
        data = json.loads(result)
        assert "error" in data
        assert "schema is required" in data["error"]


class TestIdpCalibrateSchema:
    """Tests for _handle_idp_calibrate_schema param validation."""

    @pytest.mark.asyncio
    async def test_missing_plugin_id(self) -> None:
        result = await _handle_idp_calibrate_schema({"document_paths": ["/a.pdf"]})
        data = json.loads(result)
        assert "error" in data
        assert "plugin_id is required" in data["error"]

    @pytest.mark.asyncio
    async def test_missing_document_paths(self) -> None:
        result = await _handle_idp_calibrate_schema({"plugin_id": "invoices"})
        data = json.loads(result)
        assert "error" in data
        assert "document_paths is required" in data["error"]

    @pytest.mark.asyncio
    async def test_file_not_found(self) -> None:
        result = await _handle_idp_calibrate_schema({
            "plugin_id": "invoices",
            "document_paths": ["/nonexistent/a.pdf"],
        })
        data = json.loads(result)
        assert "error" in data
        assert "File not found" in data["error"]


class TestIdpGetCalibrationStatus:
    """Tests for _handle_idp_get_calibration_status param validation."""

    @pytest.mark.asyncio
    async def test_missing_plugin_id(self) -> None:
        result = await _handle_idp_get_calibration_status({})
        data = json.loads(result)
        assert "error" in data
        assert "plugin_id is required" in data["error"]


# ---------------------------------------------------------------------------
# build_tool_handler with IDP domain
# ---------------------------------------------------------------------------


class TestBuildToolHandlerIdp:
    """Tests for build_tool_handler with domain='idp'."""

    def test_build_tool_handler_idp(self) -> None:
        client = AnthropicClient(project_id="test-project", region="us-central1")
        handler = build_tool_handler(client, "idp")
        assert isinstance(handler, ToolHandler)
        # IDP tools registered
        assert "discover_api" in handler._tool_handlers
        assert "execute_api" in handler._tool_handlers
        assert "upload_document" in handler._tool_handlers
        assert "get_job_detail" in handler._tool_handlers
        assert "list_plugins" in handler._tool_handlers
        assert "get_settings" in handler._tool_handlers
        # Ravenna tools registered
        assert "read_progress" in handler._tool_handlers
        assert "write_structured_result" in handler._tool_handlers

    def test_build_tool_handler_idp_with_operativo_id(self) -> None:
        client = AnthropicClient(project_id="test-project", region="us-central1")
        handler = build_tool_handler(client, "idp", operativo_id="op-123")
        assert isinstance(handler, ToolHandler)
        # upload_document should be wrapped
        assert "upload_document" in handler._tool_handlers

    def test_build_tool_handler_unsupported_domain(self) -> None:
        client = AnthropicClient(project_id="test-project", region="us-central1")
        with pytest.raises(ValueError, match="Unsupported domain"):
            build_tool_handler(client, "unknown")

    def test_error_message_lists_supported_domains(self) -> None:
        client = AnthropicClient(project_id="test-project", region="us-central1")
        with pytest.raises(ValueError, match="'dce', 'idp'"):
            build_tool_handler(client, "nope")
