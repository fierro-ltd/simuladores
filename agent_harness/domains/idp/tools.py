"""IDP Platform API manifest: 12 operations across 3 categories."""

from __future__ import annotations

IDP_MANIFEST: dict[str, dict[str, dict]] = {
    "jobs": {
        "upload_document": {
            "description": "Upload PDF for extraction via a plugin.",
            "params": {"document_path": "str", "plugin_id": "str"},
            "returns": "dict",
        },
        "get_job_detail": {
            "description": "Full job detail with stage results.",
            "params": {"job_id": "str"},
            "returns": "dict",
        },
        "get_job_status": {
            "description": "Lightweight status poll for a job.",
            "params": {"job_id": "str"},
            "returns": "dict",
        },
        "list_jobs": {
            "description": "List jobs, optionally filtered by plugin.",
            "params": {"plugin_id": "str | None", "limit": "int"},
            "returns": "list[dict]",
        },
        "patch_job_verdict": {
            "description": "Update verdict on a completed job.",
            "params": {"job_id": "str", "verdict": "str"},
            "returns": "dict",
        },
    },
    "plugins": {
        "list_plugins": {
            "description": "List all available plugins.",
            "params": {},
            "returns": "list[dict]",
        },
        "get_plugin": {
            "description": "Get plugin configuration and schema.",
            "params": {"plugin_id": "str"},
            "returns": "dict",
        },
        "update_schema": {
            "description": "Update extraction schema for a plugin.",
            "params": {
                "plugin_id": "str",
                "schema": "dict",
                "change_description": "str",
            },
            "returns": "dict",
        },
        "calibrate_schema": {
            "description": "Start schema calibration using sample documents.",
            "params": {"plugin_id": "str", "document_paths": "list[str]"},
            "returns": "dict",
        },
        "get_calibration_status": {
            "description": "Check calibration workflow status.",
            "params": {"plugin_id": "str", "workflow_id": "str | None"},
            "returns": "dict",
        },
    },
    "settings": {
        "get_settings": {
            "description": "Get current platform settings.",
            "params": {},
            "returns": "dict",
        },
        "update_settings": {
            "description": "Update platform settings.",
            "params": {
                "extraction_mode": "str | None",
                "default_llm_model": "str | None",
                "active_plugin": "str | None",
            },
            "returns": "dict",
        },
    },
}


def discover_api(category: str | None = None) -> str:
    """Return IDP manifest text, filtered by category if given.

    Returns empty string for unknown categories.
    """
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
            lines.append(
                f"  {op_name}({params_str}) -> {op_schema['returns']}"
            )
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
    """Return all 12 IDP operation names."""
    ops: list[str] = []
    for operations in IDP_MANIFEST.values():
        ops.extend(operations.keys())
    return ops
