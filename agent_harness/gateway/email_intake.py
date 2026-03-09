"""Email intake gateway — receives classified emails from dispatch."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AttachmentRef:
    """Reference to an email attachment stored by dispatch."""
    filename: str
    storage_path: str  # GCS path from dispatch
    content_type: str
    size_bytes: int


@dataclass(frozen=True)
class EmailIntakePayload:
    """Payload from dispatch email classification."""
    email_id: str
    sender: str
    subject: str
    classification: str  # "dce" / "has" / "idp"
    attachments: list[AttachmentRef] = field(default_factory=list)
    received_at: str = ""


class EmailIntakeError(Exception):
    """Raised when email intake validation fails."""


def validate_email_payload(payload: EmailIntakePayload) -> None:
    """Validate an email intake payload.

    Raises EmailIntakeError on validation failure.
    """
    if not payload.email_id:
        raise EmailIntakeError("email_id is required")
    if not payload.sender:
        raise EmailIntakeError("sender is required")
    if not payload.classification:
        raise EmailIntakeError("classification is required")
    valid_domains = {"dce", "has", "idp"}
    if payload.classification not in valid_domains:
        raise EmailIntakeError(
            f"Unknown classification '{payload.classification}'. "
            f"Valid: {', '.join(sorted(valid_domains))}"
        )
    if not payload.attachments:
        raise EmailIntakeError("At least one attachment is required")
    for att in payload.attachments:
        if not att.filename:
            raise EmailIntakeError("Attachment filename is required")
        if not att.storage_path:
            raise EmailIntakeError("Attachment storage_path is required")


def find_pdf_attachment(payload: EmailIntakePayload) -> AttachmentRef | None:
    """Find the first PDF attachment in the payload."""
    for att in payload.attachments:
        if att.filename.lower().endswith(".pdf"):
            return att
    return None
