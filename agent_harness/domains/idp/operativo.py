"""IDP domain operativo input and output types."""

from __future__ import annotations

from dataclasses import dataclass

from agent_harness.core.operativo import OperativoStatus


@dataclass(frozen=True)
class IdpOperativoInput:
    """Input for an IDP operativo execution."""

    document_path: str              # Absolute path to PDF file
    plugin_id: str                  # IDP Platform plugin ID (e.g. "invoices")
    caller_id: str
    callback_url: str | None = None


@dataclass(frozen=True)
class IdpOperativoOutput:
    """Output from an IDP operativo execution."""

    operativo_id: str
    status: OperativoStatus
    structured_result: dict
    extraction_job_id: str | None = None
    qa_summary: str | None = None
