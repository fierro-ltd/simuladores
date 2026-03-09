"""Tests for Santos planner agent."""

from __future__ import annotations

import json

import pytest

from agent_harness.agents.santos import (
    SANTOS_SYSTEM_IDENTITY,
    SantosPlanner,
    parse_plan_json,
)
from agent_harness.agents.base import AgentConfig, BaseAgent
from agent_harness.core.plan import AgentTask, ExecutionPlan


class TestSantosSystemIdentity:
    """Tests for SANTOS_SYSTEM_IDENTITY constant."""

    def test_mentions_santos(self):
        assert "Santos" in SANTOS_SYSTEM_IDENTITY

    def test_mentions_planning(self):
        lower = SANTOS_SYSTEM_IDENTITY.lower()
        assert "plan" in lower

    def test_mentions_no_tools(self):
        lower = SANTOS_SYSTEM_IDENTITY.lower()
        assert "no tool" in lower or "without tool" in lower


class TestParsePlanJson:
    """Tests for parse_plan_json."""

    def test_valid_json_single_step(self):
        raw = json.dumps({
            "steps": [
                {"agent": "lamponne", "action": "execute_api", "params": {"endpoint": "/validate"}}
            ]
        })
        plan = parse_plan_json(raw, "op-123")
        assert isinstance(plan, ExecutionPlan)
        assert plan.operativo_id == "op-123"
        assert len(plan.tasks) == 1
        assert plan.tasks[0].agent == "lamponne"
        assert plan.tasks[0].action == "execute_api"
        assert plan.tasks[0].params == {"endpoint": "/validate"}

    def test_valid_json_multiple_steps(self):
        raw = json.dumps({
            "steps": [
                {"agent": "medina", "action": "read_pdf", "params": {}},
                {"agent": "lamponne", "action": "execute_api", "params": {"x": 1}},
                {"agent": "ravenna", "action": "synthesize", "params": {}},
            ]
        })
        plan = parse_plan_json(raw, "op-456")
        assert len(plan.tasks) == 3
        assert plan.tasks[0].agent == "medina"
        assert plan.tasks[2].agent == "ravenna"

    def test_valid_json_no_params_defaults_to_empty_dict(self):
        raw = json.dumps({
            "steps": [
                {"agent": "lamponne", "action": "run"}
            ]
        })
        plan = parse_plan_json(raw, "op-789")
        assert plan.tasks[0].params == {}

    def test_invalid_json_falls_back_to_default_plan(self):
        plan = parse_plan_json("not json at all", "op-bad")
        assert len(plan.tasks) == 6
        assert plan.tasks[0].agent == "santos"

    def test_missing_steps_key_falls_back_to_default_plan(self):
        raw = json.dumps({"plan": []})
        plan = parse_plan_json(raw, "op-bad")
        assert len(plan.tasks) == 6
        assert plan.tasks[0].agent == "santos"

    def test_empty_steps_returns_empty_plan(self):
        raw = json.dumps({"steps": []})
        plan = parse_plan_json(raw, "op-empty")
        assert plan.tasks == []


class TestSantosPlanner:
    """Tests for SantosPlanner class."""

    def test_has_no_tools(self):
        cfg = AgentConfig(
            name="santos",
            model="claude-sonnet-4-6",
            system_identity=SANTOS_SYSTEM_IDENTITY,
            domain="dce",
        )
        base = BaseAgent(config=cfg)
        planner = SantosPlanner(base_agent=base)
        assert planner.tools is None

    def test_stores_base_agent(self):
        cfg = AgentConfig(
            name="santos",
            model="claude-sonnet-4-6",
            system_identity=SANTOS_SYSTEM_IDENTITY,
            domain="dce",
        )
        base = BaseAgent(config=cfg)
        planner = SantosPlanner(base_agent=base)
        assert planner.base_agent is base
