"""Tests for the DCE domain verification checklist."""

from agent_harness.domains.dce.checklist import CPC_VERIFICATION_CHECKLIST


class TestCPCVerificationChecklist:
    def test_is_list_of_strings(self):
        assert isinstance(CPC_VERIFICATION_CHECKLIST, list)
        for item in CPC_VERIFICATION_CHECKLIST:
            assert isinstance(item, str)

    def test_has_expected_item_count(self):
        assert len(CPC_VERIFICATION_CHECKLIST) == 14

    def test_mentions_required_fields(self):
        joined = " ".join(CPC_VERIFICATION_CHECKLIST)
        assert "product_name" in joined
        assert "manufacturer" in joined
        assert "model_number" in joined
        assert "standards_referenced" in joined

    def test_mentions_injection_scan(self):
        assert any("injection" in item.lower() for item in CPC_VERIFICATION_CHECKLIST)

    def test_mentions_json_schema(self):
        assert any("JSON" in item for item in CPC_VERIFICATION_CHECKLIST)

    def test_mentions_numerical_plausibility(self):
        assert any("numerical" in item.lower() or "plausible" in item.lower() for item in CPC_VERIFICATION_CHECKLIST)

    def test_items_are_questions(self):
        for item in CPC_VERIFICATION_CHECKLIST:
            assert item.endswith("?") or item.endswith(")") or item.endswith("."), (
                f"Checklist item should be a question: {item}"
            )
