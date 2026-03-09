"""Tests for agent loop activity types."""

from __future__ import annotations

import pytest

from agent_harness.activities.agent_loop import AgentLoopInput, AgentLoopOutput


class TestAgentLoopInput:
    """Tests for AgentLoopInput frozen dataclass."""

    def test_creation_with_defaults(self):
        inp = AgentLoopInput(
            agent_name="lamponne",
            domain="dce",
            operativo_id="op-200",
            task_message="Execute validation API",
            available_tools=["execute_api", "discover_api"],
        )
        assert inp.agent_name == "lamponne"
        assert inp.domain == "dce"
        assert inp.operativo_id == "op-200"
        assert inp.task_message == "Execute validation API"
        assert inp.available_tools == ["execute_api", "discover_api"]
        assert inp.max_turns == 10

    def test_max_turns_override(self):
        inp = AgentLoopInput(
            agent_name="lamponne",
            domain="dce",
            operativo_id="op-200",
            task_message="msg",
            available_tools=[],
            max_turns=5,
        )
        assert inp.max_turns == 5

    def test_frozen(self):
        inp = AgentLoopInput(
            agent_name="lamponne",
            domain="dce",
            operativo_id="op-200",
            task_message="msg",
            available_tools=[],
        )
        with pytest.raises(AttributeError):
            inp.agent_name = "santos"


class TestAgentLoopOutput:
    """Tests for AgentLoopOutput frozen dataclass."""

    def test_creation(self):
        out = AgentLoopOutput(
            final_response="Validation complete.",
            tool_calls_made=["execute_api", "execute_api"],
            turns_used=3,
        )
        assert out.final_response == "Validation complete."
        assert out.tool_calls_made == ["execute_api", "execute_api"]
        assert out.turns_used == 3

    def test_frozen(self):
        out = AgentLoopOutput(
            final_response="Done.",
            tool_calls_made=[],
            turns_used=1,
        )
        with pytest.raises(AttributeError):
            out.turns_used = 99
