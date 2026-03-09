"""Tests for the HAS worker module."""

from __future__ import annotations

from agent_harness.workers.has import CEE_TASK_QUEUE, get_activity_list, get_workflow_list
from agent_harness.workflows.has_workflow import CEEOperativoWorkflow


def test_cee_task_queue():
    """Task queue name matches the HAS convention."""
    assert CEE_TASK_QUEUE == "has-operativo"


def test_workflow_list_contains_cee():
    """Workflow list includes CEEOperativoWorkflow."""
    workflows = get_workflow_list()
    assert CEEOperativoWorkflow in workflows
    assert len(workflows) == 1


def test_activity_list_has_7():
    """Activity list has exactly 7 activity functions (6 phases + callback)."""
    activities = get_activity_list()
    assert len(activities) == 7

    # Verify the expected function names
    names = {fn.__name__ for fn in activities}
    expected = {
        "santos_plan",
        "medina_investigate",
        "lamponne_execute",
        "santos_qa_review",
        "ravenna_synthesize",
        "post_job_learn",
        "deliver_callback",
    }
    assert names == expected
