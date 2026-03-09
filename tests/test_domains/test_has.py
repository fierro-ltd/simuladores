"""Tests for HAS domain types and tools."""

import pytest

from agent_harness.domains.has.operativo import (
    CEEOperativoInput,
    CEEOperativoOutput,
)
from agent_harness.domains.has.tools import (
    CEE_MANIFEST,
    discover_api,
    list_operations,
)
from agent_harness.core.operativo import OperativoStatus


class TestCEEOperativoInput:
    def test_creation(self):
        inp = CEEOperativoInput(
            document_path="/path/to/doc.pdf",
            document_filename="attestation.pdf",
            caller_id="user-1",
            document_type="attestation",
        )
        assert inp.document_type == "attestation"
        assert inp.guideline_version == "latest"
        assert inp.audit_scope == "full"

    def test_partial_audit(self):
        inp = CEEOperativoInput(
            document_path="/p.pdf", document_filename="f.pdf",
            caller_id="u1", document_type="facture",
            audit_scope="partial",
        )
        assert inp.audit_scope == "partial"

    def test_frozen(self):
        inp = CEEOperativoInput(
            document_path="/p.pdf", document_filename="f.pdf",
            caller_id="u1", document_type="devis",
        )
        with pytest.raises(AttributeError):
            inp.document_type = "changed"


class TestCEEOperativoOutput:
    def test_creation(self):
        out = CEEOperativoOutput(
            operativo_id="has-001",
            status=OperativoStatus.COMPLETED,
            structured_result={"valid": True},
        )
        assert out.operativo_id == "has-001"
        assert out.status == OperativoStatus.COMPLETED

    def test_frozen(self):
        out = CEEOperativoOutput(
            operativo_id="has-1",
            status=OperativoStatus.PENDING,
            structured_result={},
        )
        with pytest.raises(AttributeError):
            out.status = OperativoStatus.FAILED


class TestCEEManifest:
    def test_has_three_categories(self):
        assert set(CEE_MANIFEST.keys()) == {"extraction", "validation", "reporting"}

    def test_total_operations(self):
        assert len(list_operations()) == 5

    def test_discover_api_all(self):
        result = discover_api()
        assert "[extraction]" in result
        assert "[validation]" in result
        assert "extract_document_text" in result

    def test_discover_api_category(self):
        result = discover_api("validation")
        assert "[validation]" in result
        assert "extraction" not in result

    def test_discover_api_unknown(self):
        assert discover_api("nonexistent") == ""


class TestCEEVerificationChecklist:
    def test_is_list_of_strings(self):
        from agent_harness.domains.has.checklist import CEE_VERIFICATION_CHECKLIST
        assert isinstance(CEE_VERIFICATION_CHECKLIST, list)
        for item in CEE_VERIFICATION_CHECKLIST:
            assert isinstance(item, str)

    def test_at_least_5_items(self):
        from agent_harness.domains.has.checklist import CEE_VERIFICATION_CHECKLIST
        assert len(CEE_VERIFICATION_CHECKLIST) >= 5

    def test_all_items_are_questions(self):
        from agent_harness.domains.has.checklist import CEE_VERIFICATION_CHECKLIST
        for item in CEE_VERIFICATION_CHECKLIST:
            assert item.endswith("?"), f"Checklist item should be a question: {item}"

    def test_contains_key_cee_terms(self):
        from agent_harness.domains.has.checklist import CEE_VERIFICATION_CHECKLIST
        combined = " ".join(CEE_VERIFICATION_CHECKLIST).lower()
        assert "document_type" in combined
        assert "guideline" in combined
        assert "audit" in combined
        assert "has" in combined
        assert "qa" in combined.lower()


class TestCEEExports:
    def test_exports_input_output(self):
        from agent_harness.domains.has import CEEOperativoInput, CEEOperativoOutput
        assert CEEOperativoInput is not None
        assert CEEOperativoOutput is not None

    def test_exports_discover_api(self):
        from agent_harness.domains.has import discover_api
        result = discover_api()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_exports_list_operations(self):
        from agent_harness.domains.has import list_operations
        ops = list_operations()
        assert isinstance(ops, list)
        assert len(ops) == 5
