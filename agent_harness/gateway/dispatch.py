"""API gateway dispatch — intake for operativos.

Validates input, generates operativo_id, and returns
the data needed to submit a workflow to Temporal.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from agent_harness.core.operativo import OperativoStatus
from agent_harness.domains.dce.operativo import CPCOperativoInput
from agent_harness.domains.has.operativo import CEEOperativoInput
from agent_harness.domains.idp.operativo import IdpOperativoInput


@dataclass(frozen=True)
class DispatchResult:
    """Result of dispatching an operativo request."""
    operativo_id: str
    status: OperativoStatus
    workflow_input: Any


class DispatchError(Exception):
    """Raised when dispatch validation fails."""


_VALID_CEE_DOCUMENT_TYPES = {"attestation", "facture", "devis"}


def dispatch_dce_operativo(
    pdf_path: str,
    pdf_filename: str,
    caller_id: str,
    callback_url: str | None = None,
    skip_navigation: bool = False,
    skip_lab_check: bool = False,
    skip_photos: bool = False,
    e2e_fast_mode: bool = False,
) -> DispatchResult:
    """Validate and dispatch a DCE operativo request.

    Returns DispatchResult with generated operativo_id and validated input.
    Raises DispatchError on validation failure.
    """
    if not pdf_path:
        raise DispatchError("pdf_path is required")
    if not pdf_filename:
        raise DispatchError("pdf_filename is required")
    if not caller_id:
        raise DispatchError("caller_id is required")
    if not pdf_filename.lower().endswith(".pdf"):
        raise DispatchError("pdf_filename must end with .pdf")

    operativo_id = f"dce-{uuid.uuid4().hex[:12]}"

    workflow_input = CPCOperativoInput(
        pdf_path=pdf_path,
        pdf_filename=pdf_filename,
        caller_id=caller_id,
        callback_url=callback_url,
        skip_navigation=skip_navigation,
        skip_lab_check=skip_lab_check,
        skip_photos=skip_photos,
        e2e_fast_mode=e2e_fast_mode,
    )

    return DispatchResult(
        operativo_id=operativo_id,
        status=OperativoStatus.PENDING,
        workflow_input=workflow_input,
    )


def dispatch_has_operativo(
    document_path: str,
    document_filename: str,
    caller_id: str,
    document_type: str,
    guideline_version: str = "latest",
    audit_scope: str = "full",
    callback_url: str | None = None,
) -> DispatchResult:
    """Validate and dispatch a HAS operativo request.

    Returns DispatchResult with generated operativo_id and validated input.
    Raises DispatchError on validation failure.
    """
    if not document_path:
        raise DispatchError("document_path is required")
    if not document_filename:
        raise DispatchError("document_filename is required")
    if not caller_id:
        raise DispatchError("caller_id is required")
    if document_type not in _VALID_CEE_DOCUMENT_TYPES:
        raise DispatchError(
            f"document_type must be one of {sorted(_VALID_CEE_DOCUMENT_TYPES)}, "
            f"got '{document_type}'"
        )

    operativo_id = f"has-{uuid.uuid4().hex[:12]}"

    workflow_input = CEEOperativoInput(
        document_path=document_path,
        document_filename=document_filename,
        caller_id=caller_id,
        document_type=document_type,
        guideline_version=guideline_version,
        audit_scope=audit_scope,
        callback_url=callback_url,
    )

    return DispatchResult(
        operativo_id=operativo_id,
        status=OperativoStatus.PENDING,
        workflow_input=workflow_input,
    )


def dispatch_idp_operativo(
    document_path: str,
    plugin_id: str,
    caller_id: str,
    callback_url: str | None = None,
) -> DispatchResult:
    """Validate and dispatch an IDP operativo request.

    Returns DispatchResult with generated operativo_id and validated input.
    Raises DispatchError on validation failure.
    """
    if not document_path:
        raise DispatchError("document_path is required")
    if not plugin_id:
        raise DispatchError("plugin_id is required")
    if not caller_id:
        raise DispatchError("caller_id is required")

    operativo_id = f"idp-{uuid.uuid4().hex[:12]}"

    workflow_input = IdpOperativoInput(
        document_path=document_path,
        plugin_id=plugin_id,
        caller_id=caller_id,
        callback_url=callback_url,
    )

    return DispatchResult(
        operativo_id=operativo_id,
        status=OperativoStatus.PENDING,
        workflow_input=workflow_input,
    )
