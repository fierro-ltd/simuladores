"""Tests for SimpleOrchestrator (Brigada B)."""

import pytest

from agent_harness.agents.brigada_b import (
    SIMPLE_ORCHESTRATOR_IDENTITY,
    SimpleOrchestratorConfig,
)
from agent_harness.agents.brigada_b.simple_orchestrator import (
    is_simple_operativo,
)
from agent_harness.agents.base import BaseAgent, AgentConfig


class TestSimpleOrchestratorIdentity:
    def test_mentions_simple(self):
        assert "simple" in SIMPLE_ORCHESTRATOR_IDENTITY.lower()

    def test_mentions_brigada_b(self):
        assert "Brigada B" in SIMPLE_ORCHESTRATOR_IDENTITY

    def test_mentions_single_pass(self):
        assert "single pass" in SIMPLE_ORCHESTRATOR_IDENTITY

    def test_mentions_progress(self):
        assert "PROGRESS" in SIMPLE_ORCHESTRATOR_IDENTITY

    def test_mentions_no_investigation(self):
        assert "investigation" in SIMPLE_ORCHESTRATOR_IDENTITY.lower()


class TestSimpleOrchestratorConfig:
    def test_defaults(self):
        config = SimpleOrchestratorConfig(domain="dce")
        assert config.domain == "dce"
        assert config.max_turns == 5
        assert config.model == "claude-sonnet-4-6"

    def test_custom(self):
        config = SimpleOrchestratorConfig(
            domain="has", max_turns=3, model="claude-haiku-4-5",
        )
        assert config.domain == "has"
        assert config.max_turns == 3

    def test_frozen(self):
        config = SimpleOrchestratorConfig(domain="dce")
        with pytest.raises(AttributeError):
            config.domain = "changed"


class TestIsSimpleOperativo:
    def test_simple(self):
        assert is_simple_operativo("simple") is True

    def test_standard(self):
        assert is_simple_operativo("standard") is False

    def test_unknown(self):
        assert is_simple_operativo("complex") is False

    def test_empty(self):
        assert is_simple_operativo("") is False


class TestSimpleOrchestratorPrompt:
    def test_builds_prompt(self):
        config = AgentConfig(
            name="simple_orchestrator",
            model="claude-sonnet-4-6",
            system_identity=SIMPLE_ORCHESTRATOR_IDENTITY,
            domain="dce",
        )
        agent = BaseAgent(config)
        prompt = agent.build_prompt(
            user_message="Convert this PDF to JSON",
            domain_memory="# DCE Domain",
            semantic_patterns=[],
            session_state="",
        )
        assert "SimpleOrchestrator" in prompt["system"]
