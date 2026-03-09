"""DCE citation completeness helpers for workflow integration."""

from __future__ import annotations

import json
import re
from typing import Any

from agent_harness.domains.dce.citation_registry import build_completeness_report

def derive_provided_citations(extracted_data: dict[str, Any]) -> list[str]:
    """Derive citation strings from extracted DCE data/regulations.

    Handles multiple extraction formats: structured_fields.regulations,
    Citations, citations, and inline regulation text.
    """
    citations: list[str] = []
    seen: set[str] = set()

    def _add(c: str) -> None:
        c = _normalize_citation(c)
        if c and c not in seen:
            seen.add(c)
            citations.append(c)

    # From structured_fields (Medina/local extraction)
    sf = extracted_data.get("structured_fields", extracted_data)
    if isinstance(sf, dict):
        regs = sf.get("regulations") or sf.get("Citations") or sf.get("citations")
        if isinstance(regs, list):
            for r in regs:
                if isinstance(r, str):
                    _add(r)
                elif isinstance(r, dict) and "citation_text" in r:
                    _add(r["citation_text"])
        elif isinstance(regs, str):
            for part in regs.split(";"):
                _add(part.strip())

    # Top-level extraction keys (DCE Backend format)
    for key in ("Citations", "citations", "regulations"):
        val = extracted_data.get(key)
        if isinstance(val, list):
            for r in val:
                if isinstance(r, str):
                    _add(r)
                elif isinstance(r, dict) and "citation_text" in r:
                    _add(r["citation_text"])
        elif isinstance(val, str):
            for part in val.split(";"):
                _add(part.strip())

    return citations


def _normalize_citation(c: str) -> str:
    """Normalize citation string for deduplication."""
    c = c.strip()
    if not c:
        return ""
    # Collapse whitespace
    c = " ".join(c.split())
    return c


def derive_product_profile(extracted_data: dict[str, Any]) -> dict[str, Any]:
    """Derive product profile from extracted DCE data.

    Builds a minimal profile for citation applicability checks.
    """
    sf = extracted_data.get("structured_fields", extracted_data)
    if not isinstance(sf, dict):
        sf = extracted_data if isinstance(extracted_data, dict) else {}

    profile: dict[str, Any] = {}
    for key in (
        "product_description",
        "product_name",
        "brand_name",
        "Product",
        "product_type",
        "category",
    ):
        val = sf.get(key) or extracted_data.get(key)
        if val and isinstance(val, str):
            profile["product_description"] = val
            break

    if "product_description" not in profile:
        profile["product_description"] = sf.get("product_description") or ""

    profile["brand_name"] = sf.get("brand_name") or extracted_data.get("brand_name") or ""
    profile["place_of_manufacture"] = (
        sf.get("place_of_manufacture") or extracted_data.get("place_of_manufacture") or ""
    )
    desc = str(profile.get("product_description", "")).lower()

    # Category + applicability flags (deterministic heuristics)
    if re.search(r"\bdresser\b|\bclothing\s*storage\b", desc):
        profile["product_category"] = "dresser"
    elif re.search(r"\btoy\b", desc):
        profile["product_category"] = "toy"
    else:
        profile["product_category"] = "unknown"

    profile["is_toy"] = profile["product_category"] == "toy"
    profile["is_childcare"] = bool(
        re.search(r"\bdresser\b|\bcrib\b|\bbassinet\b|\bchanging\s*table\b|\bhigh\s*chair\b", desc)
    )

    # Parse age hints into a single max-age month field used by registry logic.
    age_text = " ".join(
        str(sf.get(k, "")) for k in ("age_grade", "age_range", "age")
    ) + " " + desc
    m = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*(?:months?|mo\b)", age_text, re.I)
    if m:
        profile["age_months"] = int(m.group(2))
    else:
        m = re.search(r"under\s*(\d+)\s*(?:months?|mo\b)", age_text, re.I)
        if m:
            profile["age_months"] = int(m.group(1))
    return profile


def compute_completeness_report(
    input_snapshot_json: str,
    *,
    vision_extraction_json: str = "",
) -> str:
    """Compute citation completeness report from Medina extraction context.

    Produces a JSON string artifact-like payload with:
    - provided_citations: list of derived citation strings
    - product_profile: minimal product profile
    - citation_classifications: per-citation classification (KNOWN/UNKNOWN/NON_CPC_OPERATIONAL)
    - unknown_count: count of unknown citations
    - web_verification_recommended: True when ambiguity present (unknown citations, scope uncertainty)

    Args:
        input_snapshot_json: JSON string of Medina's InputSnapshot or extraction.
        vision_extraction_json: Optional vision extraction for cross-reference.

    Returns:
        JSON string of the completeness report.
    """
    try:
        data = json.loads(input_snapshot_json)
    except json.JSONDecodeError:
        data = {}

    if not isinstance(data, dict):
        data = {}

    # Handle InputSnapshot format (has structured_fields) vs raw extraction
    extracted = data.get("structured_fields", data)
    if isinstance(extracted, dict):
        pass
    elif isinstance(data, dict):
        extracted = data
    else:
        extracted = {}

    provided = derive_provided_citations(extracted if isinstance(extracted, dict) else {})
    product_profile = derive_product_profile(extracted if isinstance(extracted, dict) else {})

    report = build_completeness_report(product_profile, provided)
    classifications: list[dict[str, str]] = (
        [{"citation": c, "classification": "MISSING_CPC_CITATION"} for c in report.missing]
        + [{"citation": raw, "classification": "INVALID_CPC_CITATION"} for raw, _ in report.invalid]
        + [
            {"citation": raw, "classification": "NON_CPC_OPERATIONAL_REQUIREMENT"}
            for raw, _ in report.non_citable_references
        ]
    )

    # Ambiguity/review triggers: invalid refs, non-citable refs, or thin context.
    scope_uncertainty = (
        not (product_profile.get("product_description") or "").strip()
        or (len(provided) == 0 and not vision_extraction_json)
    )
    ambiguous_count = len(report.invalid) + len(report.non_citable_references)
    unknown_count = len(report.invalid)

    web_verification_recommended = ambiguous_count > 0 or scope_uncertainty

    payload = {
        "provided_citations": provided,
        "product_profile": product_profile,
        "required_citations": report.required,
        "covered_citations": report.covered,
        "missing_citations": report.missing,
        "invalid_citations": [{"citation": raw, "reason": reason} for raw, reason in report.invalid],
        "non_cpc_operational_references": [
            {"citation": raw, "reason": reason} for raw, reason in report.non_citable_references
        ],
        "citation_classifications": classifications,
        "unknown_count": unknown_count,
        "web_verification_recommended": web_verification_recommended,
    }
    return json.dumps(payload, default=str)
