"""IDP API manifest — placeholder for future IDP operations."""

from __future__ import annotations

NAVIGATOR_MANIFEST: dict[str, dict[str, dict]] = {
    "identification": {
        "identify_applicable_standards": {
            "description": "Identify applicable test standards for a product.",
            "params": {"product_description": "str", "target_markets": "list[str]"},
            "returns": "list[dict]",
        },
        "classify_product_category": {
            "description": "Classify product into testing category.",
            "params": {"product_description": "str"},
            "returns": "dict",
        },
    },
    "planning": {
        "generate_test_plan": {
            "description": "Generate a test plan based on applicable standards.",
            "params": {"standards": "list[dict]", "product_data": "dict"},
            "returns": "dict",
        },
        "estimate_timeline": {
            "description": "Estimate testing timeline and costs.",
            "params": {"test_plan": "dict"},
            "returns": "dict",
        },
    },
    "matching": {
        "find_capable_labs": {
            "description": "Find labs capable of performing required tests.",
            "params": {"test_requirements": "list[dict]", "region": "str"},
            "returns": "list[dict]",
        },
    },
}


def discover_api(category: str | None = None) -> str:
    """Return IDP manifest text, filtered by category if given."""
    if category is not None:
        if category not in NAVIGATOR_MANIFEST:
            return ""
        categories = {category: NAVIGATOR_MANIFEST[category]}
    else:
        categories = NAVIGATOR_MANIFEST

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
    """Return all IDP operation names."""
    ops: list[str] = []
    for operations in NAVIGATOR_MANIFEST.values():
        ops.extend(operations.keys())
    return ops
