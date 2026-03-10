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
