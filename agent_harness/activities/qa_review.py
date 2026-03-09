"""Santos QA review Temporal activity types."""

from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass(frozen=True)
class QAReviewInput:
    """Input for the Santos QA review activity."""
    operativo_id: str
    domain: str
    input_snapshot_json: str
    raw_output_json: str
    max_correction_attempts: int = 3
    verify_checklist: Optional[Tuple[str, ...]] = field(default=None)
    vision_extraction_json: str = ""
    citation_completeness_report_json: str = ""
    web_verification_evidence_json: str = ""


@dataclass(frozen=True)
class QAReviewOutput:
    """Output from the Santos QA review activity."""
    operativo_id: str
    qa_report_json: str
    corrections_applied: int
    final_status: str  # "COMPLETED" / "NEEDS_REVIEW"
    phase_result: str
    corrected_citation_matrix_json: str = ""
