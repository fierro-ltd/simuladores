"""Tests for Medina investigator agent."""


from agent_harness.agents.medina import (
    MEDINA_SYSTEM_IDENTITY,
    MEDINA_TOOLS,
)


class TestMedinaIdentity:
    def test_mentions_medina(self):
        assert "Medina" in MEDINA_SYSTEM_IDENTITY

    def test_mentions_investigator(self):
        assert "Investigat" in MEDINA_SYSTEM_IDENTITY

    def test_mentions_injection_scanning(self):
        assert "injection" in MEDINA_SYSTEM_IDENTITY.lower()

    def test_mentions_opus_mandatory(self):
        assert "Opus" in MEDINA_SYSTEM_IDENTITY

    def test_mentions_halt_on_high_risk(self):
        assert "HALT" in MEDINA_SYSTEM_IDENTITY or "halt" in MEDINA_SYSTEM_IDENTITY.lower()


class TestMedinaTools:
    def test_has_three_tools(self):
        assert len(MEDINA_TOOLS) == 3

    def test_has_extract_pdf_text(self):
        names = [t["name"] for t in MEDINA_TOOLS]
        assert "extract_pdf_text" in names

    def test_has_scan_content(self):
        names = [t["name"] for t in MEDINA_TOOLS]
        assert "scan_content" in names

    def test_has_extract_cpc_data(self):
        names = [t["name"] for t in MEDINA_TOOLS]
        assert "extract_cpc_data" in names

    def test_tool_schemas_valid(self):
        for tool in MEDINA_TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert tool["input_schema"]["type"] == "object"
