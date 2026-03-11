"""Integration tests for the full stack configuration."""


from agent_harness.workers.dce import CPC_TASK_QUEUE, get_workflow_list, get_activity_list
from agent_harness.gateway.app import create_app
from agent_harness.gateway.dispatch import dispatch_dce_operativo


def test_worker_task_queue():
    assert CPC_TASK_QUEUE == "dce-operativo"


def test_worker_has_all_components():
    workflows = get_workflow_list()
    activities = get_activity_list()
    assert len(workflows) == 2
    assert len(activities) == 10


def test_gateway_creates_app():
    app = create_app()
    routes = [r.path for r in app.routes]
    assert "/health" in routes
    assert "/operativo/dce" in routes
    assert "/operativo/{operativo_id}/status" in routes


def test_dispatch_to_workflow_input():
    result = dispatch_dce_operativo(
        pdf_path="/data/test.pdf",
        pdf_filename="test.pdf",
        caller_id="user-001",
    )
    assert result.operativo_id.startswith("dce-")
    assert result.workflow_input.pdf_path == "/data/test.pdf"


def test_full_import_chain():
    """Verify all runtime modules can be imported without errors."""
    from agent_harness.llm import AnthropicClient, ToolHandler
    from agent_harness.agents import (
        SantosPlanner, MedinaInvestigator, LamponneExecutor,
        RavennaSynthesizer, SantosQAReviewer,
    )
    from agent_harness.workflows.operativo_workflow import CPCOperativoWorkflow
    from agent_harness.workers.dce import CPC_TASK_QUEUE

    assert AnthropicClient is not None
    assert ToolHandler is not None
    assert SantosPlanner is not None
    assert MedinaInvestigator is not None
    assert LamponneExecutor is not None
    assert RavennaSynthesizer is not None
    assert SantosQAReviewer is not None
    assert CPCOperativoWorkflow is not None
    assert CPC_TASK_QUEUE == "dce-operativo"
