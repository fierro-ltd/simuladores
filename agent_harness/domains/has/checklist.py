"""HAS domain verification checklist — deterministic checks for QA review."""

CEE_VERIFICATION_CHECKLIST: list[str] = [
    "Does the output identify the correct document_type (attestation, facture, or devis)?",
    "Are all extracted HAS fields compliant with the referenced guideline version?",
    "Is the audit scope (full or partial) correctly reflected in the validation coverage?",
    "Do extracted field values match the source document (spot-check at least 3 fields against input_snapshot)?",
    "Is the structured_result format valid JSON with the expected HAS schema?",
    "Are all numerical values (energy savings, surface areas, financial amounts) within plausible ranges?",
    "Does the QA summary accurately count blocking vs warning vs info issues for the HAS audit?",
]
