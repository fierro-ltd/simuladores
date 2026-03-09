"""IDP domain verification checklist — deterministic checks for QA review."""

NAVIGATOR_VERIFICATION_CHECKLIST: list[str] = [
    "Are all applicable standards correctly identified for the product and target markets?",
    "Does the test plan cover every identified standard with specific test methods?",
    "Is the product classification consistent with the product description and category?",
    "Do the matched labs have verified capabilities for all required tests?",
    "Does the structured_result conform to the expected JSON schema with all required fields?",
    "Are timeline estimates and cost projections within plausible ranges for the test scope?",
    "Does the QA summary accurately reflect blocking vs warning vs informational findings?",
]
