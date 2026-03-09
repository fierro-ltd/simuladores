"""Tests for IDP domain types and tools."""

import pytest

from agent_harness.domains.idp.operativo import (
    IdpOperativoInput,
    IdpOperativoOutput,
)
from agent_harness.domains.idp.tools import (
    NAVIGATOR_MANIFEST,
    discover_api,
    list_operations,
)
from agent_harness.core.operativo import OperativoStatus


class TestIdpOperativoInput:
    def test_creation(self):
        inp = IdpOperativoInput(
            product_description="Children's toy robot",
            caller_id="user-1",
        )
        assert inp.product_description == "Children's toy robot"
        assert inp.target_markets is None
        assert inp.product_category is None

    def test_with_markets(self):
        inp = IdpOperativoInput(
            product_description="LED light",
            caller_id="u1",
            target_markets=["US", "EU"],
        )
        assert inp.target_markets == ["US", "EU"]

    def test_frozen(self):
        inp = IdpOperativoInput(
            product_description="toy", caller_id="u1",
        )
        with pytest.raises(AttributeError):
            inp.product_description = "changed"


class TestIdpOperativoOutput:
    def test_creation(self):
        out = IdpOperativoOutput(
            operativo_id="nav-001",
            status=OperativoStatus.COMPLETED,
            structured_result={"standards": []},
        )
        assert out.operativo_id == "nav-001"

    def test_frozen(self):
        out = IdpOperativoOutput(
            operativo_id="nav-1",
            status=OperativoStatus.PENDING,
            structured_result={},
        )
        with pytest.raises(AttributeError):
            out.status = OperativoStatus.FAILED


class TestNavigatorManifest:
    def test_has_three_categories(self):
        assert set(NAVIGATOR_MANIFEST.keys()) == {"identification", "planning", "matching"}

    def test_total_operations(self):
        assert len(list_operations()) == 5

    def test_discover_api_all(self):
        result = discover_api()
        assert "[identification]" in result
        assert "[planning]" in result
        assert "identify_applicable_standards" in result

    def test_discover_api_category(self):
        result = discover_api("matching")
        assert "[matching]" in result
        assert "identification" not in result

    def test_discover_api_unknown(self):
        assert discover_api("nonexistent") == ""


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


class TestNavigatorExports:
    def test_input_exported(self):
        from agent_harness.domains.idp import IdpOperativoInput

        inp = IdpOperativoInput(
            product_description="LED bulb", caller_id="u1",
        )
        assert inp.product_description == "LED bulb"

    def test_output_exported(self):
        from agent_harness.domains.idp import IdpOperativoOutput

        out = IdpOperativoOutput(
            operativo_id="nav-1",
            status=OperativoStatus.COMPLETED,
            structured_result={},
        )
        assert out.operativo_id == "nav-1"

    def test_discover_api_exported(self):
        from agent_harness.domains.idp import discover_api

        result = discover_api()
        assert "[identification]" in result

    def test_list_operations_exported(self):
        from agent_harness.domains.idp import list_operations

        ops = list_operations()
        assert len(ops) == 5
