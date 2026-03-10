"""Tests for the IDP worker module."""

from __future__ import annotations

from agent_harness.workers.idp import IDP_TASK_QUEUE, get_activity_list, get_workflow_list
from agent_harness.workflows.idp_workflow import IdpOperativoWorkflow


def test_idp_task_queue():
    """Task queue name matches the IDP convention."""
    assert IDP_TASK_QUEUE == "idp-operativo"


def test_workflow_list_contains_navigator():
    """Workflow list includes IdpOperativoWorkflow."""
    workflows = get_workflow_list()
    assert IdpOperativoWorkflow in workflows
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
