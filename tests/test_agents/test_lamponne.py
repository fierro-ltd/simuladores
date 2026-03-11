"""Tests for Lamponne executor agent configuration."""


from agent_harness.agents.lamponne import (
    LAMPONNE_SYSTEM_IDENTITY,
    LAMPONNE_TOOLS,
)


class TestLamponneSystemIdentity:
    def test_mentions_lamponne(self):
        assert "Lamponne" in LAMPONNE_SYSTEM_IDENTITY

    def test_mentions_executor(self):
        assert "executor" in LAMPONNE_SYSTEM_IDENTITY.lower()

    def test_mentions_discover_api(self):
        assert "discover_api" in LAMPONNE_SYSTEM_IDENTITY

    def test_mentions_execute_api(self):
        assert "execute_api" in LAMPONNE_SYSTEM_IDENTITY


class TestLamponneTools:
    def test_exactly_two_tools(self):
        assert len(LAMPONNE_TOOLS) == 2

    def test_tool_names(self):
        names = {t["name"] for t in LAMPONNE_TOOLS}
        assert names == {"discover_api", "execute_api"}

    def test_discover_api_schema(self):
        tool = next(t for t in LAMPONNE_TOOLS if t["name"] == "discover_api")
        params = tool["input_schema"]
        assert "category" in params["properties"]
        cat_schema = params["properties"]["category"]
        assert "enum" in cat_schema
        assert set(cat_schema["enum"]) == {
            "extraction",
            "navigation",
            "validation",
            "tools",
            "global",
        }

    def test_discover_api_category_optional(self):
        tool = next(t for t in LAMPONNE_TOOLS if t["name"] == "discover_api")
        params = tool["input_schema"]
        required = params.get("required", [])
        assert "category" not in required

    def test_execute_api_requires_operation_and_params(self):
        tool = next(t for t in LAMPONNE_TOOLS if t["name"] == "execute_api")
        params = tool["input_schema"]
        assert "operation" in params["properties"]
        assert "params" in params["properties"]
        assert "operation" in params["required"]
        assert "params" in params["required"]
