"""Tests for Temporal search attributes."""

import pytest

from agent_harness.workflows.search_attributes import (
    SearchAttribute,
    SearchAttributeType,
    OPERATIVO_SEARCH_ATTRIBUTES,
    build_search_attributes,
)


class TestSearchAttribute:
    def test_creation(self):
        attr = SearchAttribute(
            name="TestAttr",
            attribute_type=SearchAttributeType.KEYWORD,
            description="test",
        )
        assert attr.name == "TestAttr"

    def test_frozen(self):
        attr = SearchAttribute(
            name="x", attribute_type=SearchAttributeType.TEXT, description="y",
        )
        with pytest.raises(AttributeError):
            attr.name = "changed"


class TestStandardAttributes:
    def test_has_six_attributes(self):
        assert len(OPERATIVO_SEARCH_ATTRIBUTES) == 6

    def test_attribute_names(self):
        names = {a.name for a in OPERATIVO_SEARCH_ATTRIBUTES}
        assert "OperativoDomain" in names
        assert "OperativoId" in names
        assert "OperativoStatus" in names
        assert "CurrentPhase" in names
        assert "CallerID" in names
        assert "HasBlockingIssues" in names

    def test_types_correct(self):
        by_name = {a.name: a for a in OPERATIVO_SEARCH_ATTRIBUTES}
        assert by_name["OperativoDomain"].attribute_type == SearchAttributeType.KEYWORD
        assert by_name["CurrentPhase"].attribute_type == SearchAttributeType.INT
        assert by_name["HasBlockingIssues"].attribute_type == SearchAttributeType.BOOL


class TestBuildSearchAttributes:
    def test_basic(self):
        attrs = build_search_attributes("op-1", "dce")
        assert attrs["OperativoId"] == "op-1"
        assert attrs["OperativoDomain"] == "dce"
        assert attrs["OperativoStatus"] == "PENDING"
        assert attrs["CurrentPhase"] == 0
        assert attrs["HasBlockingIssues"] is False

    def test_with_all_fields(self):
        attrs = build_search_attributes(
            "op-2", "has", status="RUNNING",
            current_phase=3, caller_id="user-1",
            has_blocking=True,
        )
        assert attrs["OperativoStatus"] == "RUNNING"
        assert attrs["CurrentPhase"] == 3
        assert attrs["CallerID"] == "user-1"
        assert attrs["HasBlockingIssues"] is True

    def test_no_caller_id(self):
        attrs = build_search_attributes("op-1", "dce")
        assert "CallerID" not in attrs
