"""Tests for the DCE worker module."""

from __future__ import annotations

from agent_harness.workers.dce import CPC_TASK_QUEUE, get_activity_list, get_workflow_list
from agent_harness.workflows.cortex import CortexBulletinWorkflow
from agent_harness.workflows.operativo_workflow import CPCOperativoWorkflow


def test_cpc_task_queue():
    """Task queue name matches the DCE convention."""
    assert CPC_TASK_QUEUE == "dce-operativo"


def test_workflow_list_contains_cpc():
    """Workflow list includes CPCOperativoWorkflow and CortexBulletinWorkflow."""
    workflows = get_workflow_list()
    assert CPCOperativoWorkflow in workflows
    assert CortexBulletinWorkflow in workflows
    assert len(workflows) == 2


def test_activity_list_has_10():
    """Activity list has exactly 10 activity functions (6 phases + vision + web_verify + callback + cortex bulletin)."""
    activities = get_activity_list()
    assert len(activities) == 10

    # Verify the expected function names
    names = {fn.__name__ for fn in activities}
    expected = {
        "santos_plan",
        "medina_investigate",
        "gemini_vision_extract",
        "lamponne_execute",
        "cpc_web_verify",
        "santos_qa_review",
        "ravenna_synthesize",
        "post_job_learn",
        "deliver_callback",
        "cortex_generate_bulletin",
    }
    assert names == expected
