# IDP Domain Connection to IDP Platform Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Connect the IDP domain in the agent harness to the real IDP Platform API at `https://idp-platform-template.demos.fierro.co.uk`, replacing the placeholder "Navigator" manifest with operations that map to the actual document extraction platform.

**Architecture:** The IDP Platform is a document extraction system with plugins, jobs, schemas, and calibration. The harness wraps it the same way DCE wraps the DCE Backend — tool handlers in `factory.py` make HTTP calls to the IDP Platform API. The operativo input changes from `product_description` to `document_path` + `plugin_id`, matching the platform's job submission model. Bearer token auth is required for all API calls.

**Tech Stack:** Python 3.11+, httpx (async HTTP), Temporal.io workflows, frozen dataclasses, pytest

---

## Context: IDP Platform API (v0.6.0)

Base URL: configurable via `IDP_PLATFORM_URL` env var (default: `http://localhost:8100`)

**Jobs** (document processing):
- `POST /api/jobs` — Upload document (multipart: file + plugin_id) → 202 JobResponse
- `GET /api/jobs` — List jobs (optional: plugin_id, limit)
- `GET /api/jobs/{job_id}` — Full job detail with stage results
- `GET /api/jobs/{job_id}/status` — Lightweight status poll
- `GET /api/jobs/{job_id}/file` — Download uploaded document
- `PATCH /api/jobs/{job_id}` — Update verdict
- `DELETE /api/jobs/{job_id}` — Remove job

**Plugins** (extraction schemas):
- `GET /api/plugins` — List all plugins
- `GET /api/plugins/{plugin_id}` — Get plugin config + schema
- `PUT /api/plugins/{plugin_id}/schema` — Update schema (versioned)
- `POST /api/plugins/{plugin_id}/calibrate` — Start calibration with sample docs
- `GET /api/plugins/{plugin_id}/calibrate/status` — Check calibration status
- `GET /api/plugins/{plugin_id}/schema/export` — Export schema as YAML
- `GET /api/plugins/{plugin_id}/schema/versions` — List schema versions

**Settings:**
- `GET /api/settings` — Get current settings
- `PUT /api/settings` — Update settings (extraction_mode, models, etc.)

**Auth:** Bearer token via `IDP_PLATFORM_TOKEN` env var.

**Key schemas:** JobResponse (id, plugin_id, filename, status, verdict, stages, page_count, error), PluginResponse (id, name, schema, calibration_status, stages), StageResultResponse (stage, status, summary, details, issues, metrics).

---

## Task 1: Rewrite IDP Tools Manifest

**Files:**
- Modify: `agent_harness/domains/idp/tools.py` (full rewrite)
- Test: `tests/test_domains/test_idp.py` (update manifest tests)

**Step 1: Write the failing tests**

Update `tests/test_domains/test_idp.py` to test the new manifest structure. Replace the existing manifest tests with:

```python
# In tests/test_domains/test_idp.py — replace manifest-related tests

def test_idp_manifest_categories():
    """IDP manifest has jobs, plugins, and settings categories."""
    from agent_harness.domains.idp.tools import IDP_MANIFEST
    assert set(IDP_MANIFEST.keys()) == {"jobs", "plugins", "settings"}

def test_idp_manifest_jobs_operations():
    """Jobs category has upload, get_detail, get_status, list, patch_verdict operations."""
    from agent_harness.domains.idp.tools import IDP_MANIFEST
    expected_ops = {
        "upload_document",
        "get_job_detail",
        "get_job_status",
        "list_jobs",
        "patch_job_verdict",
    }
    assert set(IDP_MANIFEST["jobs"].keys()) == expected_ops

def test_idp_manifest_plugins_operations():
    """Plugins category has list, get, update_schema, calibrate, calibration_status operations."""
    from agent_harness.domains.idp.tools import IDP_MANIFEST
    expected_ops = {
        "list_plugins",
        "get_plugin",
        "update_schema",
        "calibrate_schema",
        "get_calibration_status",
    }
    assert set(IDP_MANIFEST["plugins"].keys()) == expected_ops

def test_idp_manifest_settings_operations():
    """Settings category has get and update operations."""
    from agent_harness.domains.idp.tools import IDP_MANIFEST
    expected_ops = {"get_settings", "update_settings"}
    assert set(IDP_MANIFEST["settings"].keys()) == expected_ops

def test_idp_discover_api_all():
    """discover_api with no category returns all 12 operations."""
    from agent_harness.domains.idp.tools import discover_api
    result = discover_api()
    assert "[jobs]" in result
    assert "[plugins]" in result
    assert "[settings]" in result
    assert "upload_document" in result

def test_idp_discover_api_filtered():
    """discover_api with category='jobs' returns only jobs operations."""
    from agent_harness.domains.idp.tools import discover_api
    result = discover_api(category="jobs")
    assert "[jobs]" in result
    assert "[plugins]" not in result

def test_idp_discover_api_unknown():
    """discover_api with unknown category returns empty string."""
    from agent_harness.domains.idp.tools import discover_api
    assert discover_api(category="nonexistent") == ""

def test_idp_list_operations():
    """list_operations returns all 12 operation names."""
    from agent_harness.domains.idp.tools import list_operations
    ops = list_operations()
    assert len(ops) == 12
    assert "upload_document" in ops
    assert "list_plugins" in ops

def test_idp_get_operation_schema():
    """get_operation_schema returns schema for known operation, None for unknown."""
    from agent_harness.domains.idp.tools import get_operation_schema
    schema = get_operation_schema("upload_document")
    assert schema is not None
    assert "description" in schema
    assert "params" in schema

    assert get_operation_schema("nonexistent") is None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_domains/test_idp.py -v`
Expected: FAIL — `IDP_MANIFEST` not found, `get_operation_schema` not importable

**Step 3: Implement the new manifest**

Rewrite `agent_harness/domains/idp/tools.py`:

```python
"""IDP Platform API manifest — maps harness tools to IDP Platform REST endpoints."""

from __future__ import annotations

IDP_MANIFEST: dict[str, dict[str, dict]] = {
    "jobs": {
        "upload_document": {
            "description": "Upload a PDF document for extraction processing. Returns job_id for polling.",
            "params": {"document_path": "str", "plugin_id": "str"},
            "returns": "dict",  # JobResponse
        },
        "get_job_detail": {
            "description": "Get full job detail including all stage results and extracted data.",
            "params": {"job_id": "str"},
            "returns": "dict",  # JobResponse with stages
        },
        "get_job_status": {
            "description": "Lightweight status poll for a running job.",
            "params": {"job_id": "str"},
            "returns": "dict",  # JobStatusResponse
        },
        "list_jobs": {
            "description": "List processed jobs, optionally filtered by plugin.",
            "params": {"plugin_id": "str | None", "limit": "int"},
            "returns": "list[dict]",
        },
        "patch_job_verdict": {
            "description": "Update the verdict (accept/reject) on a completed job.",
            "params": {"job_id": "str", "verdict": "str"},
            "returns": "dict",
        },
    },
    "plugins": {
        "list_plugins": {
            "description": "List all available extraction plugins with their schemas and calibration status.",
            "params": {},
            "returns": "list[dict]",  # PluginListResponse
        },
        "get_plugin": {
            "description": "Get a specific plugin's configuration, schema, and processing stages.",
            "params": {"plugin_id": "str"},
            "returns": "dict",  # PluginResponse
        },
        "update_schema": {
            "description": "Update a plugin's extraction schema. Creates a new versioned entry.",
            "params": {"plugin_id": "str", "schema": "dict", "change_description": "str"},
            "returns": "dict",  # PluginResponse
        },
        "calibrate_schema": {
            "description": "Start schema calibration using sample documents. Returns workflow_id for status polling.",
            "params": {"plugin_id": "str", "document_paths": "list[str]"},
            "returns": "dict",  # CalibrationResponse
        },
        "get_calibration_status": {
            "description": "Check calibration workflow status for a plugin.",
            "params": {"plugin_id": "str", "workflow_id": "str | None"},
            "returns": "dict",  # CalibrationResponse
        },
    },
    "settings": {
        "get_settings": {
            "description": "Get current IDP platform settings (extraction mode, LLM models, active plugin).",
            "params": {},
            "returns": "dict",  # SettingsResponse
        },
        "update_settings": {
            "description": "Update IDP platform settings.",
            "params": {
                "extraction_mode": "str | None",
                "default_llm_model": "str | None",
                "active_plugin": "str | None",
            },
            "returns": "dict",  # SettingsResponse
        },
    },
}


def discover_api(category: str | None = None) -> str:
    """Return IDP manifest text, filtered by category if given."""
    if category is not None:
        if category not in IDP_MANIFEST:
            return ""
        categories = {category: IDP_MANIFEST[category]}
    else:
        categories = IDP_MANIFEST

    lines: list[str] = []
    for cat_name, operations in categories.items():
        lines.append(f"[{cat_name}]")
        for op_name, op_schema in operations.items():
            params_str = ", ".join(
                f"{pname}: {ptype}" for pname, ptype in op_schema["params"].items()
            )
            lines.append(f"  {op_name}({params_str}) -> {op_schema['returns']}")
            lines.append(f"    {op_schema['description']}")
        lines.append("")
    return "\n".join(lines)


def get_operation_schema(operation: str) -> dict | None:
    """Return the schema dict for an operation, or None if not found."""
    for operations in IDP_MANIFEST.values():
        if operation in operations:
            return operations[operation]
    return None


def list_operations() -> list[str]:
    """Return all IDP operation names."""
    ops: list[str] = []
    for operations in IDP_MANIFEST.values():
        ops.extend(operations.keys())
    return ops
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_domains/test_idp.py -v`
Expected: PASS

**Step 5: Update `__init__.py` to export `get_operation_schema`**

In `agent_harness/domains/idp/__init__.py`, add `get_operation_schema` to imports and `__all__`.

**Step 6: Commit**

```bash
git add agent_harness/domains/idp/tools.py agent_harness/domains/idp/__init__.py tests/test_domains/test_idp.py
git commit -m "feat(idp): rewrite tools manifest to match real IDP Platform API"
```

---

## Task 2: Update IDP Operativo Input/Output Types

**Files:**
- Modify: `agent_harness/domains/idp/operativo.py`
- Modify: `agent_harness/gateway/dispatch.py:123-154`
- Modify: `agent_harness/gateway/app.py:85-101`
- Test: `tests/test_domains/test_idp.py` (update operativo tests)

**Step 1: Write the failing tests**

```python
# In tests/test_domains/test_idp.py — replace operativo-related tests

def test_idp_operativo_input_document_fields():
    """IdpOperativoInput requires document_path and plugin_id."""
    from agent_harness.domains.idp.operativo import IdpOperativoInput
    inp = IdpOperativoInput(
        document_path="/tmp/invoice.pdf",
        plugin_id="invoices",
        caller_id="test-user",
    )
    assert inp.document_path == "/tmp/invoice.pdf"
    assert inp.plugin_id == "invoices"
    assert inp.caller_id == "test-user"
    assert inp.callback_url is None

def test_idp_operativo_output_extraction_result():
    """IdpOperativoOutput has extraction_result instead of test_plan_url."""
    from agent_harness.domains.idp.operativo import IdpOperativoOutput
    from agent_harness.core.operativo import OperativoStatus
    out = IdpOperativoOutput(
        operativo_id="idp-abc123",
        status=OperativoStatus.COMPLETED,
        structured_result={"fields": {"invoice_number": "INV-001"}},
        extraction_job_id="job-uuid-here",
    )
    assert out.extraction_job_id == "job-uuid-here"
    assert out.qa_summary is None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_domains/test_idp.py::test_idp_operativo_input_document_fields -v`
Expected: FAIL — `document_path` not a field

**Step 3: Update operativo.py**

```python
"""IDP domain operativo input and output types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from agent_harness.core.operativo import OperativoStatus


@dataclass(frozen=True)
class IdpOperativoInput:
    """Input for an IDP operativo execution."""

    document_path: str              # Absolute path to PDF file
    plugin_id: str                  # IDP Platform plugin ID (e.g. "invoices")
    caller_id: str
    callback_url: Optional[str] = None


@dataclass(frozen=True)
class IdpOperativoOutput:
    """Output from an IDP operativo execution."""

    operativo_id: str
    status: OperativoStatus
    structured_result: dict
    extraction_job_id: Optional[str] = None
    qa_summary: Optional[str] = None
```

**Step 4: Update dispatch.py (lines 123-154)**

Replace `dispatch_idp_operativo` to accept `document_path` and `plugin_id` instead of `product_description`:

```python
def dispatch_idp_operativo(
    document_path: str,
    plugin_id: str,
    caller_id: str,
    callback_url: str | None = None,
) -> DispatchResult:
    """Validate and dispatch an IDP operativo request."""
    if not document_path:
        raise DispatchError("document_path is required")
    if not plugin_id:
        raise DispatchError("plugin_id is required")
    if not caller_id:
        raise DispatchError("caller_id is required")

    operativo_id = f"idp-{uuid.uuid4().hex[:12]}"

    workflow_input = IdpOperativoInput(
        document_path=document_path,
        plugin_id=plugin_id,
        caller_id=caller_id,
        callback_url=callback_url,
    )

    return DispatchResult(
        operativo_id=operativo_id,
        status=OperativoStatus.PENDING,
        workflow_input=workflow_input,
    )
```

**Step 5: Update app.py IdpRequest/IdpResponse (lines 85-101)**

```python
class IdpRequest(BaseModel):
    """Request body for creating an IDP operativo."""

    document_path: str
    plugin_id: str
    caller_id: str
    callback_url: str | None = None


class IdpResponse(BaseModel):
    """Response after submitting an IDP operativo."""

    operativo_id: str
    status: str
    task_queue: str
```

**Step 6: Update the POST /operativo/idp endpoint in app.py**

Update the endpoint handler to pass `document_path` and `plugin_id` instead of `product_description` to `dispatch_idp_operativo()`.

**Step 7: Run tests to verify they pass**

Run: `pytest tests/test_domains/test_idp.py -v`
Expected: PASS

**Step 8: Commit**

```bash
git add agent_harness/domains/idp/operativo.py agent_harness/gateway/dispatch.py agent_harness/gateway/app.py tests/test_domains/test_idp.py
git commit -m "feat(idp): update operativo types for document extraction model"
```

---

## Task 3: Implement IDP Tool Handlers in factory.py

**Files:**
- Modify: `agent_harness/activities/factory.py` (add IDP handlers + update `build_tool_handler`)
- Create: `tests/test_activities/test_idp_handlers.py`

This is the core task — making the harness actually call the IDP Platform API.

**Step 1: Write the failing tests**

```python
# tests/test_activities/test_idp_handlers.py
"""Tests for IDP tool handlers."""

import json
import pytest


@pytest.mark.asyncio
async def test_handle_idp_discover_api():
    """discover_api handler returns formatted manifest text."""
    from agent_harness.activities.factory import _handle_idp_discover_api
    result = await _handle_idp_discover_api({"category": "jobs"})
    assert "[jobs]" in result
    assert "upload_document" in result


@pytest.mark.asyncio
async def test_handle_idp_discover_api_all():
    """discover_api handler with no category returns all."""
    from agent_harness.activities.factory import _handle_idp_discover_api
    result = await _handle_idp_discover_api({})
    assert "[jobs]" in result
    assert "[plugins]" in result
    assert "[settings]" in result


@pytest.mark.asyncio
async def test_handle_idp_execute_api_known_operation():
    """execute_api handler validates known operations."""
    from agent_harness.activities.factory import _handle_idp_execute_api
    result_str = await _handle_idp_execute_api({
        "operation": "list_plugins",
        "params": {},
    })
    result = json.loads(result_str)
    assert result["status"] == "executed"
    assert result["operation"] == "list_plugins"


@pytest.mark.asyncio
async def test_handle_idp_execute_api_unknown_operation():
    """execute_api handler rejects unknown operations."""
    from agent_harness.activities.factory import _handle_idp_execute_api
    result_str = await _handle_idp_execute_api({
        "operation": "nonexistent",
        "params": {},
    })
    result = json.loads(result_str)
    assert "error" in result


@pytest.mark.asyncio
async def test_handle_idp_upload_document_missing_path():
    """upload_document handler errors on missing document_path."""
    from agent_harness.activities.factory import _handle_idp_upload_document
    result_str = await _handle_idp_upload_document({})
    result = json.loads(result_str)
    assert "error" in result


@pytest.mark.asyncio
async def test_handle_idp_get_job_detail_missing_id():
    """get_job_detail handler errors on missing job_id."""
    from agent_harness.activities.factory import _handle_idp_get_job_detail
    result_str = await _handle_idp_get_job_detail({})
    result = json.loads(result_str)
    assert "error" in result


def test_build_tool_handler_idp():
    """build_tool_handler accepts 'idp' domain."""
    from unittest.mock import MagicMock
    from agent_harness.activities.factory import build_tool_handler
    client = MagicMock()
    handler = build_tool_handler(client=client, domain="idp")
    assert handler is not None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_activities/test_idp_handlers.py -v`
Expected: FAIL — `_handle_idp_discover_api` not found, `build_tool_handler` rejects "idp"

**Step 3: Implement IDP tool handlers**

Add to `agent_harness/activities/factory.py`, after the DCE section (after line 576) and before the Ravenna section (before line 579):

```python
# ---------------------------------------------------------------------------
# IDP Platform tool handler functions
# ---------------------------------------------------------------------------

from agent_harness.domains.idp.tools import (
    discover_api as idp_discover_api,
    get_operation_schema as idp_get_operation_schema,
)


async def _handle_idp_discover_api(params: dict[str, Any]) -> str:
    """Wrap discover_api from IDP tools manifest."""
    category = params.get("category")
    return idp_discover_api(category=category)


async def _handle_idp_execute_api(params: dict[str, Any]) -> str:
    """Validate operation exists via IDP manifest, return confirmation."""
    operation = params.get("operation", "")
    op_params = params.get("params", {})
    schema = idp_get_operation_schema(operation)
    if schema is None:
        return json.dumps({"error": f"Unknown IDP operation: {operation}"})
    return json.dumps({
        "status": "executed",
        "operation": operation,
        "params": op_params,
        "schema": schema,
    })


def _get_idp_client() -> tuple[str, dict[str, str]]:
    """Return (base_url, headers) for IDP Platform API."""
    base_url = os.environ.get("IDP_PLATFORM_URL", "http://localhost:8100")
    token = os.environ.get("IDP_PLATFORM_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return base_url, headers


async def _handle_idp_upload_document(params: dict[str, Any]) -> str:
    """Upload a document to the IDP Platform for extraction.

    Params:
        document_path: Absolute path to the PDF file.
        plugin_id: IDP Platform plugin ID.

    Returns:
        JSON with job_id, status, plugin_id, filename.
    """
    import httpx

    document_path = params.get("document_path", "")
    plugin_id = params.get("plugin_id", "")
    if not document_path:
        return json.dumps({"error": "document_path is required"})
    if not plugin_id:
        return json.dumps({"error": "plugin_id is required"})
    if not os.path.isfile(document_path):
        return json.dumps({"error": f"File not found: {document_path}"})

    base_url, headers = _get_idp_client()

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            with open(document_path, "rb") as f:
                resp = await client.post(
                    f"{base_url}/api/jobs",
                    files={"file": (os.path.basename(document_path), f, "application/pdf")},
                    data={"plugin_id": plugin_id},
                    headers=headers,
                )
            resp.raise_for_status()
            return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": f"IDP upload failed: {exc}"})


async def _handle_idp_get_job_detail(params: dict[str, Any]) -> str:
    """Get full job detail from IDP Platform.

    Params:
        job_id: UUID of the job.

    Returns:
        JSON with full job detail including stage results.
    """
    import httpx

    job_id = params.get("job_id", "")
    if not job_id:
        return json.dumps({"error": "job_id is required"})

    base_url, headers = _get_idp_client()

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(
                f"{base_url}/api/jobs/{job_id}",
                headers=headers,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": f"IDP get_job_detail failed: {exc}"})


async def _handle_idp_get_job_status(params: dict[str, Any]) -> str:
    """Lightweight status poll for an IDP job.

    Params:
        job_id: UUID of the job.

    Returns:
        JSON with id, status, verdict, current_stage, updated_at.
    """
    import httpx

    job_id = params.get("job_id", "")
    if not job_id:
        return json.dumps({"error": "job_id is required"})

    base_url, headers = _get_idp_client()

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{base_url}/api/jobs/{job_id}/status",
                headers=headers,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": f"IDP get_job_status failed: {exc}"})


async def _handle_idp_list_jobs(params: dict[str, Any]) -> str:
    """List jobs from IDP Platform."""
    import httpx

    base_url, headers = _get_idp_client()
    query_params: dict[str, Any] = {}
    if params.get("plugin_id"):
        query_params["plugin_id"] = params["plugin_id"]
    if params.get("limit"):
        query_params["limit"] = params["limit"]

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{base_url}/api/jobs",
                params=query_params,
                headers=headers,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": f"IDP list_jobs failed: {exc}"})


async def _handle_idp_patch_job_verdict(params: dict[str, Any]) -> str:
    """Update verdict on a completed IDP job."""
    import httpx

    job_id = params.get("job_id", "")
    verdict = params.get("verdict", "")
    if not job_id:
        return json.dumps({"error": "job_id is required"})
    if not verdict:
        return json.dumps({"error": "verdict is required"})

    base_url, headers = _get_idp_client()

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(
                f"{base_url}/api/jobs/{job_id}",
                json={"verdict": verdict},
                headers=headers,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": f"IDP patch_job_verdict failed: {exc}"})


async def _handle_idp_list_plugins(params: dict[str, Any]) -> str:
    """List all plugins from IDP Platform."""
    import httpx

    base_url, headers = _get_idp_client()

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{base_url}/api/plugins", headers=headers)
            resp.raise_for_status()
            return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": f"IDP list_plugins failed: {exc}"})


async def _handle_idp_get_plugin(params: dict[str, Any]) -> str:
    """Get a specific plugin from IDP Platform."""
    import httpx

    plugin_id = params.get("plugin_id", "")
    if not plugin_id:
        return json.dumps({"error": "plugin_id is required"})

    base_url, headers = _get_idp_client()

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{base_url}/api/plugins/{plugin_id}",
                headers=headers,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": f"IDP get_plugin failed: {exc}"})


async def _handle_idp_update_schema(params: dict[str, Any]) -> str:
    """Update a plugin's extraction schema."""
    import httpx

    plugin_id = params.get("plugin_id", "")
    schema = params.get("schema")
    change_description = params.get("change_description", "")
    if not plugin_id:
        return json.dumps({"error": "plugin_id is required"})
    if not schema:
        return json.dumps({"error": "schema is required"})

    base_url, headers = _get_idp_client()

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.put(
                f"{base_url}/api/plugins/{plugin_id}/schema",
                json={"schema": schema, "change_description": change_description},
                headers=headers,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": f"IDP update_schema failed: {exc}"})


async def _handle_idp_calibrate_schema(params: dict[str, Any]) -> str:
    """Start schema calibration with sample documents."""
    import httpx

    plugin_id = params.get("plugin_id", "")
    document_paths = params.get("document_paths", [])
    if not plugin_id:
        return json.dumps({"error": "plugin_id is required"})
    if not document_paths:
        return json.dumps({"error": "document_paths is required"})

    base_url, headers = _get_idp_client()

    try:
        files = []
        for path in document_paths:
            if not os.path.isfile(path):
                return json.dumps({"error": f"File not found: {path}"})
            files.append(("files", (os.path.basename(path), open(path, "rb"), "application/pdf")))

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{base_url}/api/plugins/{plugin_id}/calibrate",
                files=files,
                headers=headers,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        # Note: file handles are closed when files list goes out of scope
    except Exception as exc:
        return json.dumps({"error": f"IDP calibrate_schema failed: {exc}"})


async def _handle_idp_get_calibration_status(params: dict[str, Any]) -> str:
    """Check calibration status for a plugin."""
    import httpx

    plugin_id = params.get("plugin_id", "")
    if not plugin_id:
        return json.dumps({"error": "plugin_id is required"})

    base_url, headers = _get_idp_client()
    query_params: dict[str, str] = {}
    if params.get("workflow_id"):
        query_params["workflow_id"] = params["workflow_id"]

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{base_url}/api/plugins/{plugin_id}/calibrate/status",
                params=query_params,
                headers=headers,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": f"IDP get_calibration_status failed: {exc}"})


async def _handle_idp_get_settings(params: dict[str, Any]) -> str:
    """Get IDP Platform settings."""
    import httpx

    base_url, headers = _get_idp_client()

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{base_url}/api/settings", headers=headers)
            resp.raise_for_status()
            return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": f"IDP get_settings failed: {exc}"})


async def _handle_idp_update_settings(params: dict[str, Any]) -> str:
    """Update IDP Platform settings."""
    import httpx

    base_url, headers = _get_idp_client()
    body: dict[str, Any] = {}
    for key in ("extraction_mode", "default_llm_model", "active_plugin"):
        if params.get(key) is not None:
            body[key] = params[key]

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.put(
                f"{base_url}/api/settings",
                json=body,
                headers=headers,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": f"IDP update_settings failed: {exc}"})


_IDP_TOOL_HANDLERS = {
    "discover_api": _handle_idp_discover_api,
    "execute_api": _handle_idp_execute_api,
    "upload_document": _handle_idp_upload_document,
    "get_job_detail": _handle_idp_get_job_detail,
    "get_job_status": _handle_idp_get_job_status,
    "list_jobs": _handle_idp_list_jobs,
    "patch_job_verdict": _handle_idp_patch_job_verdict,
    "list_plugins": _handle_idp_list_plugins,
    "get_plugin": _handle_idp_get_plugin,
    "update_schema": _handle_idp_update_schema,
    "calibrate_schema": _handle_idp_calibrate_schema,
    "get_calibration_status": _handle_idp_get_calibration_status,
    "get_settings": _handle_idp_get_settings,
    "update_settings": _handle_idp_update_settings,
}
```

**Step 4: Update `build_tool_handler` to support IDP domain**

Replace lines 665-666 in `factory.py`:

```python
def build_tool_handler(
    client: AnthropicClient,
    domain: str,
    operativo_id: str | None = None,
) -> ToolHandler:
    """Build ToolHandler with domain-specific tool handlers."""
    if domain == "dce":
        handlers = {**_CPC_TOOL_HANDLERS, **_RAVENNA_TOOL_HANDLERS}
        if operativo_id is not None:
            base_extract = handlers["extract_pdf_text"]

            async def _extract_with_operativo(params: dict[str, Any]) -> str:
                merged = dict(params)
                merged["operativo_id"] = operativo_id
                return await base_extract(merged)

            handlers["extract_pdf_text"] = _extract_with_operativo
    elif domain == "idp":
        handlers = {**_IDP_TOOL_HANDLERS, **_RAVENNA_TOOL_HANDLERS}
        if operativo_id is not None:
            base_upload = handlers["upload_document"]

            async def _upload_with_operativo(params: dict[str, Any]) -> str:
                merged = dict(params)
                merged["operativo_id"] = operativo_id
                return await base_upload(merged)

            handlers["upload_document"] = _upload_with_operativo
    else:
        raise ValueError(f"Unsupported domain: {domain}. Supported: 'dce', 'idp'.")
    return ToolHandler(client=client, tool_handlers=handlers)
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_activities/test_idp_handlers.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add agent_harness/activities/factory.py tests/test_activities/test_idp_handlers.py
git commit -m "feat(idp): implement IDP Platform tool handlers in factory"
```

---

## Task 4: Update IDP Domain Memory and Checklist

**Files:**
- Modify: `agent_harness/domains/idp/IDP.md`
- Modify: `agent_harness/domains/idp/checklist.py`

**Step 1: Rewrite IDP.md**

```markdown
# IDP Domain Memory

## Overview
Intelligent Document Processing — extracts structured data from documents using configurable plugins. Each plugin defines an extraction schema that determines what fields to extract. The IDP Platform processes documents through multiple stages (classification, extraction, validation) and returns structured results with per-stage details.

## Core Workflow
1. A document (PDF) is uploaded to a plugin via `upload_document`
2. The platform processes it through the plugin's configured stages
3. Each stage produces a result with status, summary, details, issues, and metrics
4. The final job has a status (pending/running/completed/failed) and optional verdict

## Key Concepts
- **Plugin**: A document type definition with an extraction schema and processing stages
- **Schema**: JSON structure defining fields to extract (versioned, calibratable)
- **Calibration**: Automated schema refinement using sample documents (runs as Temporal workflow)
- **Job**: A single document processing run — has stages, status, and verdict
- **Verdict**: Human or agent review decision (accept/reject) on extracted data
- **Stage**: A processing step (e.g., classification, extraction, validation) with its own result

## Error Patterns
- Schema mismatch: plugin schema doesn't match document structure → low extraction confidence
- Missing fields: required schema fields not found in document → stage issues flagged
- Calibration drift: schema calibrated on different document format than submitted
- Plugin misconfiguration: wrong stages or model assignment for document type

## API Surface
The IDP domain wraps the IDP Platform REST API (19 endpoints). All tool calls go through PolicyChain before execution. Bearer token authentication required.
```

**Step 2: Rewrite checklist.py**

```python
"""IDP domain verification checklist — deterministic checks for QA review."""

IDP_VERIFICATION_CHECKLIST: list[str] = [
    "Was the correct plugin selected for the document type?",
    "Did all extraction stages complete without errors?",
    "Are all required schema fields present in the extraction result?",
    "Do extracted field values match visible content in the source document?",
    "Are confidence scores for extracted fields above acceptable thresholds?",
    "Were any stage issues flagged that require human review?",
    "Does the structured_result conform to the plugin's extraction schema?",
    "Is the job status consistent with the stage results (no silent failures)?",
    "Does the QA summary accurately reflect blocking vs warning vs informational findings?",
]
```

**Step 3: Update checklist import in tests if referenced by old name**

Check and update any imports of `NAVIGATOR_VERIFICATION_CHECKLIST` → `IDP_VERIFICATION_CHECKLIST`.

**Step 4: Run tests**

Run: `pytest tests/test_domains/test_idp.py -v`
Expected: PASS (after updating test references)

**Step 5: Commit**

```bash
git add agent_harness/domains/idp/IDP.md agent_harness/domains/idp/checklist.py tests/test_domains/test_idp.py
git commit -m "feat(idp): update domain memory and verification checklist for IDP Platform"
```

---

## Task 5: Update IDP Workflow for Document Extraction Model

**Files:**
- Modify: `agent_harness/workflows/idp_workflow.py`
- Test: `tests/test_workflows/test_idp_workflow.py`

**Step 1: Write updated tests**

```python
# In tests/test_workflows/test_idp_workflow.py — update tests

def test_build_plan_input_uses_document_path():
    """Plan input references document_path and plugin_id, not product_description."""
    # Build workflow, verify PlannerInput.pdf_description mentions the document
    # not a product description
    pass  # Exact test depends on build_plan_input implementation

def test_build_investigate_input_passes_document():
    """Investigation input passes document_path for Medina to scan."""
    # Unlike the old IDP workflow which passed empty pdf_path,
    # the new one should pass the actual document for injection scanning
    pass
```

**Step 2: Update `idp_workflow.py`**

Key changes to the workflow:
1. `build_plan_input` — use `input.document_path` and `input.plugin_id` in the pdf_description
2. `build_investigate_input` — pass `input.document_path` and filename to Medina (IDP now HAS a document, unlike the old Navigator model)
3. `build_output` — include `extraction_job_id` from execution results

The workflow phase structure (Santos → Medina → Lamponne → Santos QA → Ravenna → Post-job) stays the same. The change is that Medina now has a real document to scan for injection, and Lamponne's tools are the IDP Platform operations.

**Step 3: Run tests**

Run: `pytest tests/test_workflows/test_idp_workflow.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add agent_harness/workflows/idp_workflow.py tests/test_workflows/test_idp_workflow.py
git commit -m "feat(idp): update workflow for document extraction model"
```

---

## Task 6: Update IDP Worker Task Queue Naming

**Files:**
- Modify: `agent_harness/workers/idp.py`
- Modify: `agent_harness/gateway/router.py` (update registry)
- Test: `tests/test_workers/test_idp_worker.py`

**Step 1: Update task queue name**

In `workers/idp.py`, change task queue from `"nav-operativo"` to `"idp-operativo"` (consistent with the domain name, like DCE uses `"dce-operativo"`).

**Step 2: Update router registration**

In `gateway/router.py`, change:
```python
registry.register("idp", "idp-operativo", "IdpWorkflow")
```

**Step 3: Update dispatch operativo_id prefix**

Already done in Task 2 — changed from `nav-` to `idp-`.

**Step 4: Update tests**

In `tests/test_workers/test_idp_worker.py`, verify task queue = `"idp-operativo"`.

**Step 5: Run tests**

Run: `pytest tests/test_workers/test_idp_worker.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add agent_harness/workers/idp.py agent_harness/gateway/router.py tests/test_workers/test_idp_worker.py
git commit -m "refactor(idp): rename task queue from nav-operativo to idp-operativo"
```

---

## Task 7: Run Full Test Suite and Fix Breakage

**Step 1: Run all tests**

Run: `pytest tests/ -v --tb=short`

**Step 2: Fix any import errors**

Old code may reference `NAVIGATOR_MANIFEST`, `NAVIGATOR_VERIFICATION_CHECKLIST`, `product_description` fields, or `nav-` prefixes. Find and fix all references.

**Step 3: Run cache tests**

Run: `pytest tests/cache_tests/ -v`
Expected: PASS — prompt layer ordering must not be broken

**Step 4: Run injection tests**

Run: `pytest tests/injection_tests/ -v`
Expected: PASS — injection guard is domain-independent

**Step 5: Commit**

```bash
git add -u
git commit -m "fix(idp): resolve all test breakage from IDP domain rewrite"
```

---

## Task 8: Add Integration Smoke Test

**Files:**
- Create: `tests/integration/test_idp_smoke.py`

**Step 1: Write integration test**

```python
"""Smoke test: IDP domain can dispatch, build workflow input, and construct tool handler."""

import pytest
from unittest.mock import MagicMock

from agent_harness.domains.idp.operativo import IdpOperativoInput, IdpOperativoOutput
from agent_harness.domains.idp.tools import discover_api, list_operations, get_operation_schema
from agent_harness.gateway.dispatch import dispatch_idp_operativo
from agent_harness.activities.factory import build_tool_handler
from agent_harness.core.operativo import OperativoStatus


def test_idp_full_dispatch_flow():
    """Dispatch creates valid operativo_id and workflow input."""
    result = dispatch_idp_operativo(
        document_path="/tmp/test.pdf",
        plugin_id="invoices",
        caller_id="smoke-test",
    )
    assert result.operativo_id.startswith("idp-")
    assert result.status == OperativoStatus.PENDING
    assert result.workflow_input.document_path == "/tmp/test.pdf"
    assert result.workflow_input.plugin_id == "invoices"


def test_idp_tool_handler_construction():
    """Tool handler builds for IDP domain with all expected tools."""
    client = MagicMock()
    handler = build_tool_handler(client=client, domain="idp", operativo_id="idp-test123")
    assert handler is not None


def test_idp_manifest_completeness():
    """All 12 operations are discoverable and have schemas."""
    ops = list_operations()
    assert len(ops) == 12
    for op in ops:
        schema = get_operation_schema(op)
        assert schema is not None, f"Missing schema for {op}"
        assert "description" in schema
        assert "params" in schema
        assert "returns" in schema


def test_idp_discover_api_has_all_categories():
    """discover_api returns text covering all three categories."""
    text = discover_api()
    for category in ("jobs", "plugins", "settings"):
        assert f"[{category}]" in text
```

**Step 2: Run integration test**

Run: `pytest tests/integration/test_idp_smoke.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/integration/test_idp_smoke.py
git commit -m "test(idp): add integration smoke test for IDP domain"
```

---

## Summary

| Task | What | Files Changed |
|------|------|---------------|
| 1 | Rewrite tools manifest | `domains/idp/tools.py`, `domains/idp/__init__.py`, tests |
| 2 | Update operativo types + gateway | `operativo.py`, `dispatch.py`, `app.py`, tests |
| 3 | Implement tool handlers | `factory.py` (add ~350 lines), new test file |
| 4 | Update domain memory + checklist | `IDP.md`, `checklist.py` |
| 5 | Update workflow | `idp_workflow.py`, tests |
| 6 | Rename task queue | `workers/idp.py`, `router.py`, tests |
| 7 | Fix all test breakage | Various |
| 8 | Integration smoke test | New test file |

**Environment variables needed:**
- `IDP_PLATFORM_URL` — Base URL of IDP Platform (default: `http://localhost:8100`)
- `IDP_PLATFORM_TOKEN` — Bearer token for IDP Platform API auth
