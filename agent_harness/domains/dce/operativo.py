"""DCE domain operativo input and output types."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from agent_harness.core.operativo import OperativoStatus


@dataclass(frozen=True)
class CPCOperativoInput:
    """Input for a DCE operativo execution."""

    pdf_path: str
    pdf_filename: str
    caller_id: str
    callback_url: Optional[str] = None
    skip_navigation: bool = False
    skip_lab_check: bool = False
    skip_photos: bool = False
    # Fast-mode for non-production e2e validation runs.
    e2e_fast_mode: bool = False


@dataclass(frozen=True)
class CPCOperativoOutput:
    """Output from a DCE operativo execution."""

    operativo_id: str
    status: OperativoStatus
    structured_result: Dict[str, Any]
    report_url: Optional[str] = None
    qa_summary: Optional[str] = None
