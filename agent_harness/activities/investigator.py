"""Medina investigator Temporal activity types."""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class InvestigatorInput:
    """Input for the Medina investigation activity."""
    operativo_id: str
    domain: str
    pdf_path: str
    pdf_filename: str


@dataclass(frozen=True)
class InvestigatorOutput:
    """Output from the Medina investigation activity."""
    operativo_id: str
    input_snapshot_json: str
    injection_risk: str  # "none" / "low" / "high"
    phase_result: str
    halted: bool = False


@dataclass(frozen=True)
class InputSnapshot:
    """Ground-truth document snapshot built by Medina."""
    operativo_id: str
    pdf_filename: str
    injection_scan_risk: str
    structured_fields: Dict[str, str]
    raw_text_hash: str
