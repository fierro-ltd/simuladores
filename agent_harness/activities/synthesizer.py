"""Ravenna synthesizer Temporal activity types — Phase 5."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SynthesizerInput:
    """Input for the Ravenna synthesis activity."""
    operativo_id: str
    domain: str
    progress_entries: str  # All PROGRESS.md content
    raw_output_json: str
    qa_report_json: str
    caller_id: str
    corrected_citation_matrix_json: str = ""
    citation_completeness_report_json: str = ""
    web_verification_evidence_json: str = ""


@dataclass(frozen=True)
class QASummary:
    """Summary of QA results for structured_result."""
    total_checks: int
    blocking: int
    warnings: int
    info: int
    corrections_applied: int


@dataclass(frozen=True)
class SynthesizerOutput:
    """Output from the Ravenna synthesis activity."""
    operativo_id: str
    structured_result_json: str
    report_url: str
    phase_result: str
    delivery_permitted: bool = True
