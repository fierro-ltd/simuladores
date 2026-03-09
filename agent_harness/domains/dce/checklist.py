"""DCE domain verification checklist — deterministic checks for QA review."""

CPC_VERIFICATION_CHECKLIST: list[str] = [
    # Existing field-level checks
    "Does the output contain all required DCE fields (product_name, manufacturer, model_number, standards_referenced)?",
    "Do extracted values match the source PDF (spot-check at least 3 fields against input_snapshot)?",
    "Is the structured_result format valid JSON with the expected schema?",
    "Were any DCE validation rules violated (check standards compliance)?",
    "Is the injection scan result correctly reflected in the output status?",
    "Are all numerical values (weights, dimensions, test results) within plausible ranges?",
    "Does the QA summary accurately count blocking vs warning vs info issues?",
    # Citation matrix review checks
    "For each citation marked MISSING or FAIL: is the rationale factually accurate? (e.g. '16 CFR 1252 does not exist' is wrong — it exists as an exemption determination, just not a certifiable rule)",
    "Are any citations flagged as 'Missing From DCE' that are actually procedural/operational requirements, not substantive safety rules? (e.g. 16 CFR § 1107.21 governs periodic testing procedures, not DCE citations)",
    "Are any subsection-level citations (e.g. § 1303.2, § 1261.2) incorrectly flagged as 'Missing From DCE'? compliance's approved citation list uses part-level citations (16 CFR Part 1303, 16 CFR Part 1261), not subsections.",
    "Are Canadian SOR regulations (SOR-2018-83, SOR-2021-148, SOR-2022-122) correctly identified as invalid on a US compliance?",
    "Are EPA regulations (40 CFR Part 770) correctly identified as not belonging on a compliance, even if the underlying requirement is applicable to the product?",
    "Are compliance Section references (e.g. 'compliance Section 101') correctly flagged as needing statutory citation format (e.g. '15 U.S.C. § 1278a')?",
    "Is ASTM F963 correctly evaluated? It requires both 16 CFR Part 1250 AND specific applicable section numbers. Also verify product applicability (e.g. a dresser is not a toy).",
]
