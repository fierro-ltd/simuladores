"""Tests for DCE tools manifest."""


from agent_harness.domains.dce.tools import (
    CPC_MANIFEST,
    discover_api,
    get_operation_schema,
    list_operations,
)

EXPECTED_CATEGORIES = {"extraction", "navigation", "validation", "tools", "global"}


class TestManifestStructure:
    def test_manifest_has_five_categories(self):
        assert set(CPC_MANIFEST.keys()) == EXPECTED_CATEGORIES

    def test_list_operations_returns_29(self):
        ops = list_operations()
        assert len(ops) == 29

    def test_list_operations_returns_strings(self):
        ops = list_operations()
        assert all(isinstance(op, str) for op in ops)

    def test_extraction_has_9_operations(self):
        assert len(CPC_MANIFEST["extraction"]) == 9

    def test_navigation_has_4_operations(self):
        assert len(CPC_MANIFEST["navigation"]) == 4

    def test_validation_has_3_operations(self):
        assert len(CPC_MANIFEST["validation"]) == 3

    def test_tools_has_10_operations(self):
        assert len(CPC_MANIFEST["tools"]) == 10

    def test_global_has_3_operations(self):
        assert len(CPC_MANIFEST["global"]) == 3


class TestDiscoverApi:
    def test_discover_all_returns_string(self):
        result = discover_api()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_discover_all_contains_all_categories(self):
        result = discover_api()
        for cat in EXPECTED_CATEGORIES:
            assert cat in result

    def test_discover_by_category(self):
        for cat in EXPECTED_CATEGORIES:
            result = discover_api(category=cat)
            assert isinstance(result, str)
            assert len(result) > 0
            assert cat in result

    def test_discover_unknown_category_returns_empty(self):
        result = discover_api(category="nonexistent")
        assert result == ""


class TestGetOperationSchema:
    def test_known_operation_returns_dict(self):
        schema = get_operation_schema("extract_pdf_text")
        assert isinstance(schema, dict)
        assert "description" in schema
        assert "params" in schema
        assert "returns" in schema

    def test_unknown_operation_returns_none(self):
        assert get_operation_schema("nonexistent_op") is None

    def test_every_operation_has_required_fields(self):
        for op_name in list_operations():
            schema = get_operation_schema(op_name)
            assert schema is not None, f"Missing schema for {op_name}"
            assert "description" in schema, f"Missing description for {op_name}"
            assert "params" in schema, f"Missing params for {op_name}"
            assert "returns" in schema, f"Missing returns for {op_name}"
