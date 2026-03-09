"""DCE API manifest: all 28 operations across 5 categories."""

from __future__ import annotations

CPC_MANIFEST: dict[str, dict[str, dict]] = {
    "extraction": {
        "extract_pdf_text": {
            "description": "Extract raw text content from a PDF file.",
            "params": {"pdf_path": "str"},
            "returns": "str",
        },
        "extract_cpc_data": {
            "description": "Extract structured DCE data from raw PDF text.",
            "params": {"pdf_text": "str"},
            "returns": "dict",
        },
        "extract_product_profile": {
            "description": "Extract deterministic product profile from DCE data/text for citation completeness.",
            "params": {"cpc_data": "dict", "text": "str"},
            "returns": "dict",
        },
        "generate_isam_product": {
            "description": "Generate an ISAM product record from extracted DCE data.",
            "params": {"cpc_data": "dict"},
            "returns": "dict",
        },
        "fetch_isam_product": {
            "description": "Fetch an existing ISAM product record by identifier.",
            "params": {"product_id": "str"},
            "returns": "dict",
        },
        "extract_product_photos": {
            "description": "Extract product photo URLs from DCE data.",
            "params": {"cpc_data": "dict"},
            "returns": "list[str]",
        },
        "resolve_product_images": {
            "description": "Resolve and download product images from URLs.",
            "params": {"image_urls": "list[str]"},
            "returns": "list[dict]",
        },
        "validate_product_name": {
            "description": "Validate the product name against naming conventions.",
            "params": {"product_name": "str"},
            "returns": "dict",
        },
        "normalize_extraction_fields": {
            "description": "Normalize extracted DCE fields to standard format.",
            "params": {"raw_fields": "dict"},
            "returns": "dict",
        },
    },
    "navigation": {
        "navigate_decision_tree": {
            "description": "Navigate the DCE decision tree to determine applicable rules.",
            "params": {"product_data": "dict", "tree_id": "str"},
            "returns": "dict",
        },
        "analyze_section_citations": {
            "description": "Analyze section citations referenced in a DCE document.",
            "params": {"citations": "list[str]"},
            "returns": "list[dict]",
        },
        "validate_citation_applicability": {
            "description": "Validate whether citations are applicable to the product.",
            "params": {"citations": "list[str]", "product_data": "dict"},
            "returns": "dict",
        },
        "resolve_robot_ambiguities": {
            "description": "Resolve ambiguous product classifications using robot logic.",
            "params": {"product_data": "dict", "ambiguities": "list[dict]"},
            "returns": "dict",
        },
    },
    "validation": {
        "validate_cpc_elements": {
            "description": "Validate all DCE elements for completeness and correctness.",
            "params": {"cpc_data": "dict"},
            "returns": "dict",
        },
        "analyze_product_photos": {
            "description": "Analyze product photos for compliance requirements.",
            "params": {"photos": "list[dict]"},
            "returns": "dict",
        },
        "describe_product_photo": {
            "description": "Generate a textual description of a product photo.",
            "params": {"photo": "dict"},
            "returns": "str",
        },
    },
    "tools": {
        "fetch_cpsc_report_titles": {
            "description": "Fetch compliance report titles matching search criteria.",
            "params": {"query": "str"},
            "returns": "list[str]",
        },
        "fetch_cpsc_report_sections": {
            "description": "Fetch sections of a compliance report by report identifier.",
            "params": {"report_id": "str"},
            "returns": "list[dict]",
        },
        "litellm_completion": {
            "description": "Run a LiteLLM completion request for LLM-based processing.",
            "params": {"prompt": "str", "model": "str"},
            "returns": "str",
        },
        "check_lab_accreditation": {
            "description": "Check lab accreditation status for a given lab.",
            "params": {"lab_id": "str"},
            "returns": "dict",
        },
        "build_citation_lab_coverage_activity": {
            "description": "Build citation-to-lab coverage mapping for an activity.",
            "params": {"citations": "list[str]", "labs": "list[dict]"},
            "returns": "dict",
        },
        "search_lab_cpsc": {
            "description": "Search compliance lab database by query criteria.",
            "params": {"query": "str"},
            "returns": "list[dict]",
        },
        "judge_lab_match": {
            "description": "Judge whether a lab matches the required criteria.",
            "params": {"lab": "dict", "criteria": "dict"},
            "returns": "dict",
        },
        "lookup_lab_by_ids": {
            "description": "Look up lab records by their identifiers.",
            "params": {"lab_ids": "list[str]"},
            "returns": "list[dict]",
        },
        "find_lab_by_address_activity": {
            "description": "Find labs by address for a given activity.",
            "params": {"address": "str"},
            "returns": "list[dict]",
        },
        "score_lab_candidates_activity": {
            "description": "Score and rank lab candidates for an activity.",
            "params": {"candidates": "list[dict]", "criteria": "dict"},
            "returns": "list[dict]",
        },
    },
    "global": {
        "merge_assessment": {
            "description": "Merge partial assessments into a final consolidated assessment.",
            "params": {"assessments": "list[dict]"},
            "returns": "dict",
        },
        "generate_fix_suggestions_activity": {
            "description": "Generate fix suggestions for identified DCE issues.",
            "params": {"issues": "list[dict]"},
            "returns": "list[dict]",
        },
        "generate_corrected_cpc_activity": {
            "description": "Generate a corrected DCE document from original and fixes.",
            "params": {"original_cpc": "dict", "fixes": "list[dict]"},
            "returns": "dict",
        },
    },
}


def discover_api(category: str | None = None) -> str:
    """Return manifest text, filtered by category if given.

    Returns empty string for unknown categories.
    """
    if category is not None:
        if category not in CPC_MANIFEST:
            return ""
        categories = {category: CPC_MANIFEST[category]}
    else:
        categories = CPC_MANIFEST

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
    for operations in CPC_MANIFEST.values():
        if operation in operations:
            return operations[operation]
    return None


def list_operations() -> list[str]:
    """Return all 28 operation names."""
    ops: list[str] = []
    for operations in CPC_MANIFEST.values():
        ops.extend(operations.keys())
    return ops
