"""Tests for IDP domain types and tools."""

import pytest

from agent_harness.domains.idp.operativo import (
    IdpOperativoInput,
    IdpOperativoOutput,
)
from agent_harness.domains.idp.tools import (
    IDP_MANIFEST,
    discover_api,
    get_operation_schema,
    list_operations,
)
from agent_harness.core.operativo import OperativoStatus


class TestIdpOperativoInput:
    def test_creation(self):
        inp = IdpOperativoInput(
            document_path="/tmp/invoice.pdf",
            plugin_id="invoices",
            caller_id="user-1",
        )
        assert inp.document_path == "/tmp/invoice.pdf"
        assert inp.plugin_id == "invoices"
        assert inp.callback_url is None

    def test_with_callback(self):
        inp = IdpOperativoInput(
            document_path="/tmp/doc.pdf",
            plugin_id="receipts",
            caller_id="u1",
            callback_url="https://example.com/cb",
        )
        assert inp.callback_url == "https://example.com/cb"

    def test_frozen(self):
        inp = IdpOperativoInput(
            document_path="/tmp/doc.pdf", plugin_id="invoices", caller_id="u1",
        )
        with pytest.raises(AttributeError):
            inp.document_path = "changed"


class TestIdpOperativoOutput:
    def test_creation(self):
        out = IdpOperativoOutput(
            operativo_id="idp-001",
            status=OperativoStatus.COMPLETED,
            structured_result={"fields": []},
        )
        assert out.operativo_id == "idp-001"
        assert out.extraction_job_id is None

    def test_with_extraction_job_id(self):
        out = IdpOperativoOutput(
            operativo_id="idp-002",
            status=OperativoStatus.COMPLETED,
            structured_result={},
            extraction_job_id="job-abc123",
        )
        assert out.extraction_job_id == "job-abc123"

    def test_frozen(self):
        out = IdpOperativoOutput(
            operativo_id="idp-1",
            status=OperativoStatus.PENDING,
            structured_result={},
        )
        with pytest.raises(AttributeError):
            out.status = OperativoStatus.FAILED


class TestIdpManifest:
    def test_has_three_categories(self):
        assert set(IDP_MANIFEST.keys()) == {"jobs", "plugins", "settings"}

    def test_jobs_has_five_ops(self):
        assert len(IDP_MANIFEST["jobs"]) == 5

    def test_plugins_has_five_ops(self):
        assert len(IDP_MANIFEST["plugins"]) == 5

    def test_settings_has_two_ops(self):
        assert len(IDP_MANIFEST["settings"]) == 2

    def test_total_operations(self):
        assert len(list_operations()) == 12

    def test_discover_api_all(self):
        result = discover_api()
        assert "[jobs]" in result
        assert "[plugins]" in result
        assert "[settings]" in result
        assert "upload_document" in result

    def test_discover_api_category(self):
        result = discover_api(category="jobs")
        assert "[jobs]" in result
        assert "upload_document" in result
        assert "[plugins]" not in result
        assert "[settings]" not in result

    def test_discover_api_unknown(self):
        assert discover_api(category="nonexistent") == ""

    def test_get_operation_schema_found(self):
        schema = get_operation_schema("upload_document")
        assert schema is not None
        assert "description" in schema
        assert "params" in schema
        assert "returns" in schema

    def test_get_operation_schema_not_found(self):
        assert get_operation_schema("nonexistent") is None


class TestNavigatorVerificationChecklist:
    def test_is_list_of_strings(self):
        from agent_harness.domains.idp.checklist import NAVIGATOR_VERIFICATION_CHECKLIST

        assert isinstance(NAVIGATOR_VERIFICATION_CHECKLIST, list)
        for item in NAVIGATOR_VERIFICATION_CHECKLIST:
            assert isinstance(item, str)

    def test_minimum_items(self):
        from agent_harness.domains.idp.checklist import NAVIGATOR_VERIFICATION_CHECKLIST

        assert len(NAVIGATOR_VERIFICATION_CHECKLIST) >= 5

    def test_all_are_questions(self):
        from agent_harness.domains.idp.checklist import NAVIGATOR_VERIFICATION_CHECKLIST

        for item in NAVIGATOR_VERIFICATION_CHECKLIST:
            assert item.endswith("?"), f"Checklist item is not a question: {item}"

    def test_key_terms_present(self):
        from agent_harness.domains.idp.checklist import NAVIGATOR_VERIFICATION_CHECKLIST

        combined = " ".join(NAVIGATOR_VERIFICATION_CHECKLIST).lower()
        for term in ["standard", "product", "test plan"]:
            assert term in combined, f"Key term '{term}' not found in checklist"


class TestIdpExports:
    def test_input_exported(self):
        from agent_harness.domains.idp import IdpOperativoInput

        inp = IdpOperativoInput(
            document_path="/tmp/doc.pdf", plugin_id="invoices", caller_id="u1",
        )
        assert inp.document_path == "/tmp/doc.pdf"

    def test_output_exported(self):
        from agent_harness.domains.idp import IdpOperativoOutput

        out = IdpOperativoOutput(
            operativo_id="idp-1",
            status=OperativoStatus.COMPLETED,
            structured_result={},
        )
        assert out.operativo_id == "idp-1"

    def test_discover_api_exported(self):
        from agent_harness.domains.idp import discover_api

        result = discover_api()
        assert "[jobs]" in result

    def test_list_operations_exported(self):
        from agent_harness.domains.idp import list_operations

        ops = list_operations()
        assert len(ops) == 12

    def test_get_operation_schema_exported(self):
        from agent_harness.domains.idp import get_operation_schema

        schema = get_operation_schema("list_plugins")
        assert schema is not None
        assert schema["returns"] == "list[dict]"
