"""Tests for Santos plan JSON parsing resilience."""

from agent_harness.agents.santos import parse_plan_json


def test_parse_valid_json():
    raw = '{"steps": [{"agent": "medina", "action": "investigate", "params": {}}]}'
    plan = parse_plan_json(raw, "test-001")
    assert len(plan.tasks) == 1
    assert plan.tasks[0].agent == "medina"


def test_parse_json_with_trailing_comma():
    raw = '{"steps": [{"agent": "medina", "action": "investigate", "params": {},}]}'
    plan = parse_plan_json(raw, "test-002")
    assert len(plan.tasks) == 1


def test_parse_json_with_comments():
    raw = '''{"steps": [
        // This is step 1
        {"agent": "medina", "action": "investigate", "params": {}}
    ]}'''
    plan = parse_plan_json(raw, "test-003")
    assert len(plan.tasks) == 1


def test_parse_invalid_json_falls_back_to_default_plan():
    raw = "This is not JSON at all, just text."
    plan = parse_plan_json(raw, "test-004")
    assert len(plan.tasks) == 6
    assert plan.tasks[0].agent == "santos"


def test_parse_json_in_markdown_fences():
    raw = '```json\n{"steps": [{"agent": "santos", "action": "plan", "params": {}}]}\n```'
    plan = parse_plan_json(raw, "test-005")
    assert len(plan.tasks) == 1


def test_parse_json_with_surrounding_prose():
    raw = 'Here is my plan:\n\n{"steps": [{"agent": "medina", "action": "investigate", "params": {}}]}\n\nEnd.'
    plan = parse_plan_json(raw, "test-006")
    assert len(plan.tasks) == 1


def test_parse_json_preserves_url_in_params():
    """URLs in params must not be corrupted by comment stripping."""
    raw = '{"steps": [{"agent": "lamponne", "action": "call", "params": {"url": "https://api.example.com/dce"}}]}'
    plan = parse_plan_json(raw, "test-007")
    assert plan.tasks[0].params["url"] == "https://api.example.com/dce"
