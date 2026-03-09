"""HAS domain operativo input and output types."""

from __future__ import annotations

from dataclasses import dataclass

from agent_harness.core.operativo import OperativoStatus


@dataclass(frozen=True)
class CEEOperativoInput:
    """Input for a HAS operativo execution."""

    document_path: str
    document_filename: str
    caller_id: str
    document_type: str  # "attestation" / "facture" / "devis"
    guideline_version: str = "latest"
    audit_scope: str = "full"  # "full" / "partial"
    callback_url: str | None = None


@dataclass(frozen=True)
class CEEOperativoOutput:
    """Output from a HAS operativo execution."""

    operativo_id: str
    status: OperativoStatus
    structured_result: dict
    report_url: str | None = None
    qa_summary: str | None = None
