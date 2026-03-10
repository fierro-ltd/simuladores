"""Tests for gateway dispatch."""

import pytest

from agent_harness.gateway.dispatch import (
    DispatchError,
    DispatchResult,
    dispatch_dce_operativo,
)
from agent_harness.core.operativo import OperativoStatus


class TestDispatchDceOperativo:
    def test_successful_dispatch(self):
        result = dispatch_dce_operativo(
            pdf_path="/path/to/file.pdf",
            pdf_filename="file.pdf",
            caller_id="user-1",
        )
        assert isinstance(result, DispatchResult)
        assert result.operativo_id.startswith("dce-")
        assert result.status == OperativoStatus.PENDING
        assert result.workflow_input.pdf_path == "/path/to/file.pdf"

    def test_generates_unique_ids(self):
        r1 = dispatch_dce_operativo("/a.pdf", "a.pdf", "u1")
        r2 = dispatch_dce_operativo("/b.pdf", "b.pdf", "u2")
        assert r1.operativo_id != r2.operativo_id

    def test_missing_pdf_path_raises(self):
        with pytest.raises(DispatchError, match="pdf_path"):
            dispatch_dce_operativo("", "file.pdf", "u1")

    def test_missing_pdf_filename_raises(self):
        with pytest.raises(DispatchError, match="pdf_filename"):
            dispatch_dce_operativo("/path.pdf", "", "u1")

    def test_missing_caller_id_raises(self):
        with pytest.raises(DispatchError, match="caller_id"):
            dispatch_dce_operativo("/path.pdf", "file.pdf", "")

    def test_non_pdf_filename_raises(self):
        with pytest.raises(DispatchError, match=".pdf"):
            dispatch_dce_operativo("/path.txt", "file.txt", "u1")

    def test_optional_params_passed_through(self):
        result = dispatch_dce_operativo(
            "/path.pdf", "file.pdf", "u1",
            callback_url="https://example.com/callback",
            skip_navigation=True,
            skip_lab_check=True,
            skip_photos=True,
        )
        assert result.workflow_input.callback_url == "https://example.com/callback"
        assert result.workflow_input.skip_navigation is True
        assert result.workflow_input.skip_lab_check is True
        assert result.workflow_input.skip_photos is True

    def test_dispatch_result_frozen(self):
        result = dispatch_dce_operativo("/a.pdf", "a.pdf", "u1")
        with pytest.raises(AttributeError):
            result.status = OperativoStatus.RUNNING


from agent_harness.gateway.dispatch import (
    dispatch_has_operativo,
    dispatch_idp_operativo,
)


class TestDispatchHasOperativo:
    def test_successful_dispatch(self):
        result = dispatch_has_operativo(
            document_path="/path/to/doc.pdf",
            document_filename="attestation.pdf",
            caller_id="user-1",
            document_type="attestation",
        )
        assert isinstance(result, DispatchResult)
        assert result.operativo_id.startswith("has-")
        assert result.status == OperativoStatus.PENDING
        assert result.workflow_input.document_path == "/path/to/doc.pdf"
        assert result.workflow_input.document_type == "attestation"

    def test_generates_unique_ids(self):
        r1 = dispatch_has_operativo("/a.pdf", "a.pdf", "u1", "attestation")
        r2 = dispatch_has_operativo("/b.pdf", "b.pdf", "u2", "facture")
        assert r1.operativo_id != r2.operativo_id

    def test_missing_document_path_raises(self):
        with pytest.raises(DispatchError, match="document_path"):
            dispatch_has_operativo("", "file.pdf", "u1", "attestation")

    def test_missing_document_filename_raises(self):
        with pytest.raises(DispatchError, match="document_filename"):
            dispatch_has_operativo("/path.pdf", "", "u1", "attestation")

    def test_missing_caller_id_raises(self):
        with pytest.raises(DispatchError, match="caller_id"):
            dispatch_has_operativo("/path.pdf", "file.pdf", "", "attestation")

    def test_invalid_document_type_raises(self):
        with pytest.raises(DispatchError, match="document_type"):
            dispatch_has_operativo("/path.pdf", "file.pdf", "u1", "invalid_type")

    def test_valid_document_types(self):
        for doc_type in ("attestation", "facture", "devis"):
            result = dispatch_has_operativo("/p.pdf", "f.pdf", "u1", doc_type)
            assert result.workflow_input.document_type == doc_type

    def test_optional_params_passed_through(self):
        result = dispatch_has_operativo(
            "/path.pdf", "file.pdf", "u1", "attestation",
            guideline_version="v2.1",
            audit_scope="partial",
            callback_url="https://example.com/callback",
        )
        assert result.workflow_input.guideline_version == "v2.1"
        assert result.workflow_input.audit_scope == "partial"
        assert result.workflow_input.callback_url == "https://example.com/callback"


class TestDispatchIdpOperativo:
    def test_successful_dispatch(self):
        result = dispatch_idp_operativo(
            document_path="/tmp/invoice.pdf",
            plugin_id="invoices",
            caller_id="user-1",
        )
        assert isinstance(result, DispatchResult)
        assert result.operativo_id.startswith("idp-")
        assert result.status == OperativoStatus.PENDING
        assert result.workflow_input.document_path == "/tmp/invoice.pdf"
        assert result.workflow_input.plugin_id == "invoices"

    def test_generates_unique_ids(self):
        r1 = dispatch_idp_operativo("/tmp/a.pdf", "invoices", "u1")
        r2 = dispatch_idp_operativo("/tmp/b.pdf", "receipts", "u2")
        assert r1.operativo_id != r2.operativo_id

    def test_missing_document_path_raises(self):
        with pytest.raises(DispatchError, match="document_path"):
            dispatch_idp_operativo("", "invoices", "u1")

    def test_missing_plugin_id_raises(self):
        with pytest.raises(DispatchError, match="plugin_id"):
            dispatch_idp_operativo("/tmp/doc.pdf", "", "u1")

    def test_missing_caller_id_raises(self):
        with pytest.raises(DispatchError, match="caller_id"):
            dispatch_idp_operativo("/tmp/doc.pdf", "invoices", "")

    def test_optional_params_passed_through(self):
        result = dispatch_idp_operativo(
            "/tmp/doc.pdf", "invoices", "u1",
            callback_url="https://example.com/cb",
        )
        assert result.workflow_input.callback_url == "https://example.com/cb"
