"""Tests for base agent configuration and BaseAgent."""

from __future__ import annotations

import pytest

from agent_harness.agents.base import AgentConfig, AGENT_MODELS, BaseAgent


class TestAgentConfig:
    """Tests for AgentConfig dataclass."""

    def test_creation_with_all_fields(self):
        cfg = AgentConfig(
            name="santos",
            model="claude-sonnet-4-6",
            system_identity="You are Santos.",
            domain="dce",
        )
        assert cfg.name == "santos"
        assert cfg.model == "claude-sonnet-4-6"
        assert cfg.system_identity == "You are Santos."
        assert cfg.domain == "dce"

    def test_max_turns_default(self):
        cfg = AgentConfig(
            name="santos",
            model="claude-sonnet-4-6",
            system_identity="id",
            domain="dce",
        )
        assert cfg.max_turns == 10

    def test_max_turns_override(self):
        cfg = AgentConfig(
            name="santos",
            model="claude-sonnet-4-6",
            system_identity="id",
            domain="dce",
            max_turns=5,
        )
        assert cfg.max_turns == 5


class TestAgentModels:
    """Tests for AGENT_MODELS mapping."""

    def test_has_all_four_agents(self):
        assert set(AGENT_MODELS.keys()) == {"santos", "medina", "lamponne", "ravenna"}

    def test_santos_model(self):
        assert AGENT_MODELS["santos"] == "claude-sonnet-4-6"

    def test_medina_model(self):
        assert AGENT_MODELS["medina"] == "claude-sonnet-4-6"

    def test_lamponne_model(self):
        assert AGENT_MODELS["lamponne"] == "claude-sonnet-4-6"

    def test_ravenna_model(self):
        assert AGENT_MODELS["ravenna"] == "claude-sonnet-4-6"


class TestBaseAgent:
    """Tests for BaseAgent.build_prompt()."""

    def test_build_prompt_returns_required_keys(self):
        cfg = AgentConfig(
            name="santos",
            model="claude-sonnet-4-6",
            system_identity="You are Santos the planner.",
            domain="dce",
        )
        agent = BaseAgent(config=cfg)
        result = agent.build_prompt(user_message="Plan this operativo.")
        assert "system" in result
        assert "messages" in result
        assert "cache_control" in result

    def test_build_prompt_system_contains_identity(self):
        cfg = AgentConfig(
            name="santos",
            model="claude-sonnet-4-6",
            system_identity="You are Santos the planner.",
            domain="dce",
        )
        agent = BaseAgent(config=cfg)
        result = agent.build_prompt(user_message="Plan this operativo.")
        assert "Santos the planner" in result["system"]

    def test_build_prompt_messages_include_user_message(self):
        cfg = AgentConfig(
            name="santos",
            model="claude-sonnet-4-6",
            system_identity="You are Santos.",
            domain="dce",
        )
        agent = BaseAgent(config=cfg)
        result = agent.build_prompt(user_message="Plan this operativo.")
        user_msgs = [m for m in result["messages"] if m["role"] == "user"]
        assert any("Plan this operativo" in m["content"] for m in user_msgs)
