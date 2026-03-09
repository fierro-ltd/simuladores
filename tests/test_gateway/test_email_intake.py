"""Tests for email intake gateway."""

import pytest

from agent_harness.gateway.email_intake import (
    AttachmentRef,
    EmailIntakePayload,
    EmailIntakeError,
    validate_email_payload,
    find_pdf_attachment,
)


def _make_attachment(filename="test.pdf", path="gs://bucket/test.pdf"):
    return AttachmentRef(
        filename=filename,
        storage_path=path,
        content_type="application/pdf",
        size_bytes=1024,
    )


def _make_payload(**overrides):
    defaults = dict(
        email_id="email-123",
        sender="user@example.com",
        subject="DCE Review",
        classification="dce",
        attachments=[_make_attachment()],
        received_at="2026-02-21T12:00:00Z",
    )
    defaults.update(overrides)
    return EmailIntakePayload(**defaults)


class TestAttachmentRef:
    def test_creation(self):
        att = _make_attachment()
        assert att.filename == "test.pdf"
        assert att.size_bytes == 1024

    def test_frozen(self):
        att = _make_attachment()
        with pytest.raises(AttributeError):
            att.filename = "changed"


class TestEmailIntakePayload:
    def test_creation(self):
        payload = _make_payload()
        assert payload.email_id == "email-123"
        assert payload.classification == "dce"
        assert len(payload.attachments) == 1

    def test_frozen(self):
        payload = _make_payload()
        with pytest.raises(AttributeError):
            payload.email_id = "changed"


class TestValidateEmailPayload:
    def test_valid(self):
        validate_email_payload(_make_payload())

    def test_missing_email_id(self):
        with pytest.raises(EmailIntakeError, match="email_id"):
            validate_email_payload(_make_payload(email_id=""))

    def test_missing_sender(self):
        with pytest.raises(EmailIntakeError, match="sender"):
            validate_email_payload(_make_payload(sender=""))

    def test_missing_classification(self):
        with pytest.raises(EmailIntakeError, match="classification"):
            validate_email_payload(_make_payload(classification=""))

    def test_invalid_classification(self):
        with pytest.raises(EmailIntakeError, match="Unknown classification"):
            validate_email_payload(_make_payload(classification="unknown"))

    def test_no_attachments(self):
        with pytest.raises(EmailIntakeError, match="attachment"):
            validate_email_payload(_make_payload(attachments=[]))

    def test_attachment_missing_filename(self):
        bad_att = AttachmentRef(
            filename="", storage_path="gs://x", content_type="pdf", size_bytes=0,
        )
        with pytest.raises(EmailIntakeError, match="filename"):
            validate_email_payload(_make_payload(attachments=[bad_att]))

    def test_attachment_missing_path(self):
        bad_att = AttachmentRef(
            filename="test.pdf", storage_path="", content_type="pdf", size_bytes=0,
        )
        with pytest.raises(EmailIntakeError, match="storage_path"):
            validate_email_payload(_make_payload(attachments=[bad_att]))


class TestFindPdfAttachment:
    def test_finds_pdf(self):
        payload = _make_payload()
        att = find_pdf_attachment(payload)
        assert att is not None
        assert att.filename == "test.pdf"

    def test_finds_first_pdf(self):
        atts = [
            _make_attachment("doc.xlsx", "gs://x"),
            _make_attachment("cert.pdf", "gs://y"),
        ]
        payload = _make_payload(attachments=atts)
        att = find_pdf_attachment(payload)
        assert att.filename == "cert.pdf"

    def test_no_pdf(self):
        att = _make_attachment("doc.xlsx", "gs://x")
        payload = _make_payload(attachments=[att])
        assert find_pdf_attachment(payload) is None

    def test_case_insensitive(self):
        att = _make_attachment("doc.PDF", "gs://x")
        payload = _make_payload(attachments=[att])
        assert find_pdf_attachment(payload) is not None
