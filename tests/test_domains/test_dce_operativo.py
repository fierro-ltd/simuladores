"""Tests for DCE operativo domain types."""

import pytest

from agent_harness.core.operativo import OperativoStatus
from agent_harness.domains.dce.operativo import (
    CPCOperativoInput,
    CPCOperativoOutput,
)


class TestCPCOperativoInput:
    def test_required_fields(self):
        inp = CPCOperativoInput(
            pdf_path="/tmp/test.pdf",
            pdf_filename="test.pdf",
            caller_id="user-123",
        )
        assert inp.pdf_path == "/tmp/test.pdf"
        assert inp.pdf_filename == "test.pdf"
        assert inp.caller_id == "user-123"

    def test_optional_defaults(self):
        inp = CPCOperativoInput(
            pdf_path="/tmp/test.pdf",
            pdf_filename="test.pdf",
            caller_id="user-123",
        )
        assert inp.callback_url is None
        assert inp.skip_navigation is False
        assert inp.skip_lab_check is False
        assert inp.skip_photos is False
        assert inp.e2e_fast_mode is False

    def test_optional_overrides(self):
        inp = CPCOperativoInput(
            pdf_path="/tmp/test.pdf",
            pdf_filename="test.pdf",
            caller_id="user-123",
            callback_url="https://example.com/callback",
            skip_navigation=True,
            skip_lab_check=True,
            skip_photos=True,
            e2e_fast_mode=True,
        )
        assert inp.callback_url == "https://example.com/callback"
        assert inp.skip_navigation is True
        assert inp.skip_lab_check is True
        assert inp.skip_photos is True
        assert inp.e2e_fast_mode is True

    def test_frozen(self):
        inp = CPCOperativoInput(
            pdf_path="/tmp/test.pdf",
            pdf_filename="test.pdf",
            caller_id="user-123",
        )
        with pytest.raises(AttributeError):
            inp.pdf_path = "/other.pdf"


class TestCPCOperativoOutput:
    def test_required_fields(self):
        out = CPCOperativoOutput(
            operativo_id="op-001",
            status=OperativoStatus.COMPLETED,
            structured_result={"key": "value"},
        )
        assert out.operativo_id == "op-001"
        assert out.status == OperativoStatus.COMPLETED
        assert out.structured_result == {"key": "value"}

    def test_optional_defaults(self):
        out = CPCOperativoOutput(
            operativo_id="op-001",
            status=OperativoStatus.PENDING,
            structured_result={},
        )
        assert out.report_url is None
        assert out.qa_summary is None

    def test_optional_overrides(self):
        out = CPCOperativoOutput(
            operativo_id="op-001",
            status=OperativoStatus.COMPLETED,
            structured_result={"result": "ok"},
            report_url="https://example.com/report",
            qa_summary="All checks passed.",
        )
        assert out.report_url == "https://example.com/report"
        assert out.qa_summary == "All checks passed."

    def test_frozen(self):
        out = CPCOperativoOutput(
            operativo_id="op-001",
            status=OperativoStatus.RUNNING,
            structured_result={},
        )
        with pytest.raises(AttributeError):
            out.status = OperativoStatus.FAILED

    def test_status_uses_operativo_status_enum(self):
        out = CPCOperativoOutput(
            operativo_id="op-001",
            status=OperativoStatus.NEEDS_REVIEW,
            structured_result={},
        )
        assert isinstance(out.status, OperativoStatus)
        assert out.status.is_terminal is True
