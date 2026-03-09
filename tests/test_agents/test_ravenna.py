"""Tests for Ravenna synthesizer agent."""

import pytest

from agent_harness.agents.ravenna import (
    RAVENNA_SYSTEM_IDENTITY,
    RAVENNA_TOOLS,
)
from agent_harness.agents.base import BaseAgent, AgentConfig, AGENT_MODELS


class TestRavennaIdentity:
    def test_identity_mentions_ravenna(self):
        assert "Ravenna" in RAVENNA_SYSTEM_IDENTITY

    def test_identity_mentions_synthesizer(self):
        assert "Synthesizer" in RAVENNA_SYSTEM_IDENTITY

    def test_identity_mentions_structured_result(self):
        assert "structured_result" in RAVENNA_SYSTEM_IDENTITY

    def test_identity_mentions_qa_summary(self):
        assert "qa_summary" in RAVENNA_SYSTEM_IDENTITY

    def test_identity_mentions_progress(self):
        assert "PROGRESS" in RAVENNA_SYSTEM_IDENTITY

    def test_identity_mentions_permission_gated(self):
        assert "permission" in RAVENNA_SYSTEM_IDENTITY.lower()


class TestRavennaTools:
    def test_has_four_tools(self):
        assert len(RAVENNA_TOOLS) == 4

    def test_tool_names(self):
        names = {t["name"] for t in RAVENNA_TOOLS}
        assert names == {
            "read_progress",
            "load_artifact",
            "write_structured_result",
            "check_caller_permission",
        }

    def test_all_tools_have_required_fields(self):
        for tool in RAVENNA_TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert tool["input_schema"]["type"] == "object"
            assert "required" in tool["input_schema"]

    def test_load_artifact_requires_artifact_name(self):
        tool = next(t for t in RAVENNA_TOOLS if t["name"] == "load_artifact")
        assert "artifact_name" in tool["input_schema"]["required"]


class TestRavennaModel:
    def test_ravenna_uses_sonnet(self):
        assert AGENT_MODELS["ravenna"] == "claude-sonnet-4-6"

    def test_ravenna_builds_prompt(self):
        config = AgentConfig(
            name="ravenna",
            model=AGENT_MODELS["ravenna"],
            system_identity=RAVENNA_SYSTEM_IDENTITY,
            domain="dce",
        )
        agent = BaseAgent(config)
        prompt = agent.build_prompt(
            user_message="Synthesize results for op-123",
            domain_memory="# DCE Domain",
            semantic_patterns=["pattern1"],
            session_state="Phase 5 starting",
        )
        assert "Ravenna" in prompt["system"]
        assert len(prompt["messages"]) > 0
