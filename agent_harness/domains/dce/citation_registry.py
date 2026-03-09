"""DCE citation registry and completeness checker.

Deterministic citation model distinguishing:
- existence vs DCE-citable vs procedural/operational rules
- normalization/aliasing and missing/invalid coverage reporting
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class CitationType(str, Enum):
    """Semantic type of a citation for DCE purposes."""

    SUBSTANTIVE = "substantive"  # DCE-citable safety rule
    CONDITIONAL = "conditional"  # DCE-citable when product profile matches
    EXEMPTION = "exemption"  # Exists but not DCE citable (e.g. 1252)
    PROCEDURAL = "procedural"  # Operational, not DCE citable (e.g. 1107.21)
    DEFINITION = "definition"  # Subsection/definition, not standalone citable
    INVALID = "invalid"  # Not applicable to US compliance (SOR, 40 CFR, etc.)


@dataclass(frozen=True)
class CitationRule:
    """Canonical citation rule with DCE applicability semantics."""

    canonical_id: str
    citable_type: CitationType
    description: str = ""
    # Condition for conditional rules: "age_months<36" | "toy_or_childcare" | None
    condition: Optional[str] = None


# Canonical DCE citation registry
CPC_CITATION_REGISTRY: Dict[str, CitationRule] = {
    # Citable substantive (always required for children's products)
    "16 CFR Part 1261": CitationRule(
        canonical_id="16 CFR Part 1261",
        citable_type=CitationType.SUBSTANTIVE,
        description="Safety Standard for Clothing Storage Units (tip-over)",
    ),
    "16 CFR Part 1303": CitationRule(
        canonical_id="16 CFR Part 1303",
        citable_type=CitationType.SUBSTANTIVE,
        description="Ban of Lead-Containing Paint",
    ),
    "15 U.S.C. 1278a": CitationRule(
        canonical_id="15 U.S.C. 1278a",
        citable_type=CitationType.SUBSTANTIVE,
        description="Lead in substrate (compliance Section 101)",
    ),
    # Conditional: required only when profile matches
    "16 CFR Part 1501": CitationRule(
        canonical_id="16 CFR Part 1501",
        citable_type=CitationType.CONDITIONAL,
        description="Small parts (children under 36 months)",
        condition="age_months<36",
    ),
    "16 CFR Part 1307": CitationRule(
        canonical_id="16 CFR Part 1307",
        citable_type=CitationType.CONDITIONAL,
        description="Phthalates (toys and child care articles)",
        condition="toy_or_childcare",
    ),
    # Exists but not DCE citable
    "16 CFR Part 1252": CitationRule(
        canonical_id="16 CFR Part 1252",
        citable_type=CitationType.EXEMPTION,
        description="Exemption determination for engineered wood, not certifiable",
    ),
    # Procedural, not DCE citable
    "16 CFR 1107.21": CitationRule(
        canonical_id="16 CFR 1107.21",
        citable_type=CitationType.PROCEDURAL,
        description="Periodic testing procedures, not substantive safety rule",
    ),
    # Definition/subsections, not standalone citable
    "16 CFR 1303.2": CitationRule(
        canonical_id="16 CFR 1303.2",
        citable_type=CitationType.DEFINITION,
        description="Definition within Part 1303, use Part 1303",
    ),
    "16 CFR 1261.2": CitationRule(
        canonical_id="16 CFR 1261.2",
        citable_type=CitationType.DEFINITION,
        description="Definition within Part 1261, use Part 1261",
    ),
}

# Aliases: raw string patterns -> canonical_id (or None for invalid)
# Invalid/alias entries that map to None or a special handling
ALIAS_TO_CANONICAL: Dict[str, Optional[str]] = {
    "compliance Sec101": "15 U.S.C. 1278a",
    "compliance Section 101": "15 U.S.C. 1278a",
    "compliance Sec 101": "15 U.S.C. 1278a",
    "compliance Sec108": "16 CFR Part 1307",
    "compliance Section 108": "16 CFR Part 1307",
    "compliance Sec 108": "16 CFR Part 1307",
    "ASTM F2057-23": "16 CFR Part 1261",  # Incorporated into 1261
    "ASTM F2057": "16 CFR Part 1261",
    "ASTM F963-23": None,  # Requires 16 CFR Part 1250 + sections; treat as invalid/alias
    "ASTM F963": None,
}

# Patterns that are invalid on US compliance (return None, not in registry)
INVALID_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"^SOR-\d", re.I), "Canadian SOR regulations not applicable to US compliance"),
    (re.compile(r"^40\s*CFR", re.I), "EPA regulations not applicable to compliance"),
    (re.compile(r"40 CFR Part 770", re.I), "Formaldehyde rule under EPA, not compliance"),
]


def _normalize_raw(raw: str) -> str:
    """Normalize raw citation string for lookup."""
    s = raw.strip()
    # Collapse multiple spaces
    s = re.sub(r"\s+", " ", s)
    # Normalize § and "Part"
    s = re.sub(r"§\s*", "", s)
    s = re.sub(r"\bpart\b", "Part", s, flags=re.I)
    return s


def _try_match_part(raw: str) -> Optional[str]:
    """Try to match 16 CFR Part NNNN or 16 CFR NNNN.N."""
    s = _normalize_raw(raw)
    # 16 CFR Part 1261, 16 CFR 1261, 16CFR Part 1261
    m = re.match(r"16\s*CFR\s*(?:Part\s+)?(\d{4})(?:\.(\d+))?", s, re.I)
    if m:
        part = m.group(1)
        section = m.group(2)
        if section:
            key = f"16 CFR {part}.{section}"
            if key in CPC_CITATION_REGISTRY:
                return key
            # Subsection not in registry -> definition type, map to part if part exists
            part_key = f"16 CFR Part {part}"
            if part_key in CPC_CITATION_REGISTRY:
                return part_key  # Normalize subsection to part for lookup
        else:
            key = f"16 CFR Part {part}"
            if key in CPC_CITATION_REGISTRY:
                return key
    # 15 U.S.C. 1278a
    m = re.match(r"15\s*U\.?S\.?C\.?\s*§?\s*1278a", s, re.I)
    if m:
        return "15 U.S.C. 1278a"
    return None


def normalize_citation(raw: str) -> Optional[str]:
    """Normalize a raw citation to its canonical form, or None if invalid/unknown.

    Returns:
        Canonical citation ID (e.g. "16 CFR Part 1261") or None for invalid/unknown.
    """
    if not raw or not isinstance(raw, str):
        return None

    s = _normalize_raw(raw)

    # Check invalid patterns first
    for pattern, _ in INVALID_PATTERNS:
        if pattern.search(s):
            return None

    # Check explicit aliases
    for alias, canonical in ALIAS_TO_CANONICAL.items():
        if re.match(re.escape(alias), s, re.I) or alias.lower() in s.lower():
            return canonical

    # Try part/section match
    matched = _try_match_part(raw)
    if matched:
        return matched

    # Check registry by normalized key
    for canonical_id in CPC_CITATION_REGISTRY:
        if canonical_id.lower().replace(" ", "") == s.lower().replace(" ", ""):
            return canonical_id

    return None


def classify_citations(
    raw_citations: List[str],
) -> Tuple[List[str], List[Tuple[str, str]], List[Tuple[str, str]]]:
    """Classify raw citations into covered, invalid, and non_citable_references.

    Returns:
        (covered, invalid, non_citable_references)
        - covered: list of canonical IDs that are DCE-citable and provided
        - invalid: list of (raw, reason) for invalid/unknown citations
        - non_citable_references: list of (raw, reason) for exist-but-not-citable
    """
    covered: List[str] = []
    invalid: List[Tuple[str, str]] = []
    non_citable: List[Tuple[str, str]] = []

    for raw in raw_citations:
        if not raw or not isinstance(raw, str):
            continue

        canonical = normalize_citation(raw)
        if canonical is None:
            # Check if it matches invalid patterns
            for pattern, reason in INVALID_PATTERNS:
                if pattern.search(raw):
                    invalid.append((raw, reason))
                    break
            else:
                # Unknown or alias that maps to None (e.g. ASTM F963)
                invalid.append((raw, "Not a valid DCE citation or requires statutory form"))
            continue

        rule = CPC_CITATION_REGISTRY.get(canonical)
        if rule is None:
            invalid.append((raw, "Unknown citation"))
            continue

        if rule.citable_type in (CitationType.SUBSTANTIVE, CitationType.CONDITIONAL):
            covered.append(canonical)
        elif rule.citable_type == CitationType.EXEMPTION:
            non_citable.append((raw, "Exists as exemption determination, not certifiable on DCE"))
        elif rule.citable_type == CitationType.PROCEDURAL:
            non_citable.append((raw, "Procedural/operational rule, not substantive DCE citation"))
        elif rule.citable_type == CitationType.DEFINITION:
            non_citable.append((raw, "Subsection/definition; use part-level citation"))
        else:
            invalid.append((raw, "Not applicable to DCE"))

    return covered, invalid, non_citable


# Product profile: minimal dict with optional keys
# - age_months: int (max age in months, e.g. 36 for under-3)
# - is_toy: bool
# - is_childcare: bool
ProductProfile = Dict[str, Any]


def required_citations(profile: ProductProfile) -> Set[str]:
    """Return the set of canonical citation IDs required for the given product profile.

    Profile keys:
        age_months: int - max age in months (e.g. 36 for under-3)
        is_toy: bool - product is a toy
        is_childcare: bool - product is a child care article
    """
    required: Set[str] = {"16 CFR Part 1303", "15 U.S.C. 1278a"}

    product_category = str(profile.get("product_category", "")).lower()
    if product_category in {"dresser", "clothing_storage_unit"}:
        required.add("16 CFR Part 1261")

    age = profile.get("age_months")
    if age is not None and age < 36:
        required.add("16 CFR Part 1501")

    if profile.get("is_toy") or profile.get("is_childcare"):
        required.add("16 CFR Part 1307")

    return required


@dataclass
class CompletenessReport:
    """Report of citation completeness for a product profile."""

    missing: List[str] = field(default_factory=list)
    invalid: List[Tuple[str, str]] = field(default_factory=list)
    non_citable_references: List[Tuple[str, str]] = field(default_factory=list)
    covered: List[str] = field(default_factory=list)
    required: List[str] = field(default_factory=list)
    is_complete: bool = False


def build_completeness_report(
    profile: ProductProfile,
    provided_citations: List[str],
) -> CompletenessReport:
    """Build a completeness report comparing required vs provided citations.

    Args:
        profile: Product profile dict (age_months, is_toy, is_childcare)
        provided_citations: Raw citation strings from the DCE document

    Returns:
        CompletenessReport with missing, invalid, non_citable_references, covered, required.
    """
    req = required_citations(profile)
    covered, invalid, non_citable = classify_citations(provided_citations)

    covered_set = set(covered)
    missing = sorted(req - covered_set)

    return CompletenessReport(
        missing=missing,
        invalid=invalid,
        non_citable_references=non_citable,
        covered=sorted(covered_set),
        required=sorted(req),
        is_complete=len(missing) == 0,
    )
