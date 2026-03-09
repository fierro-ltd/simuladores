"""HAS API manifest — placeholder for future HAS operations."""

from __future__ import annotations

CEE_MANIFEST: dict[str, dict[str, dict]] = {
    "extraction": {
        "extract_document_text": {
            "description": "Extract raw text content from a HAS document.",
            "params": {"document_path": "str"},
            "returns": "str",
        },
        "extract_cee_fields": {
            "description": "Extract structured HAS fields from document text.",
            "params": {"document_text": "str", "document_type": "str"},
            "returns": "dict",
        },
    },
    "validation": {
        "validate_cee_elements": {
            "description": "Validate HAS elements against guideline rules.",
            "params": {"cee_data": "dict", "guideline_version": "str"},
            "returns": "dict",
        },
        "cross_reference_documents": {
            "description": "Cross-reference attestation fields against facture/devis.",
            "params": {"attestation": "dict", "reference_doc": "dict"},
            "returns": "dict",
        },
    },
    "reporting": {
        "generate_audit_report": {
            "description": "Generate an audit report for HAS validation results.",
            "params": {"validation_result": "dict"},
            "returns": "dict",
        },
    },
}


def discover_api(category: str | None = None) -> str:
    """Return HAS manifest text, filtered by category if given."""
    if category is not None:
        if category not in CEE_MANIFEST:
            return ""
        categories = {category: CEE_MANIFEST[category]}
    else:
        categories = CEE_MANIFEST

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


def list_operations() -> list[str]:
    """Return all HAS operation names."""
    ops: list[str] = []
    for operations in CEE_MANIFEST.values():
        ops.extend(operations.keys())
    return ops
