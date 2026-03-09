"""Cache-critical tests: prompt layer ordering.

These tests MUST pass in CI. A cache-breaking change is a CI failure.
The prompt layer order IS the architecture (Thariq's Law).
"""

import pytest

from agent_harness.prompt.builder import (
    PromptBuilder,
    PromptOrderViolation,
)


class TestPromptLayerOrdering:
    """Verify strict ordering: L0 → L1 → L3 → L2 → L4."""

    def test_correct_order_builds_successfully(self):
        builder = PromptBuilder()
        builder.set_system_identity("You are Santos, the orchestrator.")
        builder.set_domain_memory("# DCE Domain\nYou handle DCE documents.")
        builder.set_semantic_patterns(["Pattern 1: CFR refs need 'part'"])
        builder.set_session_state("## PLAN phase complete.")
        builder.add_working_message(role="user", content="Process this DCE.")
        messages = builder.build()
        assert len(messages) > 0

    def test_domain_before_system_raises(self):
        builder = PromptBuilder()
        with pytest.raises(PromptOrderViolation, match="Layer 1.*before.*Layer 0"):
            builder.set_domain_memory("# DCE Domain")

    def test_session_before_domain_raises(self):
        builder = PromptBuilder()
        builder.set_system_identity("System prompt.")
        with pytest.raises(PromptOrderViolation, match="Layer 2.*before.*Layer 1"):
            builder.set_session_state("Progress report.")

    def test_semantic_before_domain_raises(self):
        builder = PromptBuilder()
        builder.set_system_identity("System prompt.")
        with pytest.raises(PromptOrderViolation, match="Layer 3.*before.*Layer 1"):
            builder.set_semantic_patterns(["pattern"])

    def test_working_before_session_raises(self):
        builder = PromptBuilder()
        builder.set_system_identity("System.")
        builder.set_domain_memory("Domain.")
        builder.set_semantic_patterns([])
        with pytest.raises(PromptOrderViolation, match="Layer 4.*before.*Layer 2"):
            builder.add_working_message(role="user", content="Hello")

    def test_duplicate_system_identity_raises(self):
        builder = PromptBuilder()
        builder.set_system_identity("First.")
        with pytest.raises(PromptOrderViolation, match="already set"):
            builder.set_system_identity("Second.")


class TestPromptBuilderOutput:
    """Verify the built message structure matches Anthropic API format."""

    def _full_builder(self) -> PromptBuilder:
        builder = PromptBuilder()
        builder.set_system_identity("You are Santos.")
        builder.set_domain_memory("# DCE Domain")
        builder.set_semantic_patterns(["Pattern: always include CFR part number"])
        builder.set_session_state("## Phase 1 complete. Plan created.")
        builder.add_working_message(role="user", content="Process DCE document.")
        return builder

    def test_system_prompt_is_first(self):
        messages = self._full_builder().build()
        assert messages["system"] is not None
        assert "Santos" in messages["system"]

    def test_domain_memory_in_system(self):
        messages = self._full_builder().build()
        assert "DCE Domain" in messages["system"]

    def test_semantic_patterns_as_user_message(self):
        """Semantic patterns are injected as a user message, NOT system prompt."""
        messages = self._full_builder().build()
        user_messages = [m for m in messages["messages"] if m["role"] == "user"]
        pattern_msg = user_messages[0]
        assert "CFR part number" in pattern_msg["content"]

    def test_session_state_as_user_message(self):
        messages = self._full_builder().build()
        user_messages = [m for m in messages["messages"] if m["role"] == "user"]
        assert any("Phase 1 complete" in m["content"] for m in user_messages)

    def test_working_messages_are_last(self):
        messages = self._full_builder().build()
        last_msg = messages["messages"][-1]
        assert last_msg["content"] == "Process DCE document."

    def test_build_without_system_raises(self):
        builder = PromptBuilder()
        with pytest.raises(PromptOrderViolation, match="System identity.*required"):
            builder.build()

    def test_cache_breakpoints_present(self):
        """System + domain memory should have cache_control markers."""
        messages = self._full_builder().build()
        assert messages.get("cache_control") is not None

    def test_skip_optional_layers(self):
        """Semantic patterns and session state can be empty."""
        builder = PromptBuilder()
        builder.set_system_identity("System.")
        builder.set_domain_memory("Domain.")
        builder.set_semantic_patterns([])
        builder.set_session_state("")
        builder.add_working_message(role="user", content="Hello")
        messages = builder.build()
        assert len(messages["messages"]) >= 1
