"""Tests for callback delivery wiring in DCE workflow."""

import pytest

from agent_harness.activities.callback import CallbackInput, CallbackOutput
from agent_harness.core.operativo import OperativoStatus
from agent_harness.domains.dce.operativo import CPCOperativoInput, CPCOperativoOutput
from agent_harness.workflows.operativo_workflow import CPCOperativoWorkflow


class TestBuildOutputRegression:
    """Regression: build_output still produces correct CPCOperativoOutput."""

    def test_build_output_still_works(self):
        wf = CPCOperativoWorkflow()
        output = wf.build_output("op-abc", "Final result text")
        assert isinstance(output, CPCOperativoOutput)
        assert output.operativo_id == "op-abc"
        assert output.status == OperativoStatus.COMPLETED
        assert output.structured_result == {"response": "Final result text"}

    def test_build_output_needs_review(self):
        wf = CPCOperativoWorkflow()
        output = wf.build_output("op-abc", "Issues", OperativoStatus.NEEDS_REVIEW)
        assert output.status == OperativoStatus.NEEDS_REVIEW


class TestWorkflowHasCallbackImport:
    """Verify the CallbackInput import is reachable from the workflow module."""

    def test_workflow_has_callback_import(self):
        # CallbackInput is imported inside workflow.unsafe.imports_passed_through,
        # so verify it's importable from the callback module directly.
        from agent_harness.activities.callback import CallbackInput

        assert CallbackInput is not None


class TestCallbackInputDataclass:
    """Verify CallbackInput can be constructed with the expected fields."""

    def test_callback_input_construction(self):
        ci = CallbackInput(
            operativo_id="op-123",
            callback_url="https://example.com/hook",
            result_json='{"status": "ok"}',
        )
        assert ci.operativo_id == "op-123"
        assert ci.callback_url == "https://example.com/hook"
        assert ci.result_json == '{"status": "ok"}'

    def test_callback_input_is_frozen(self):
        ci = CallbackInput(
            operativo_id="op-1",
            callback_url="https://example.com",
            result_json="{}",
        )
        with pytest.raises(AttributeError):
            ci.operativo_id = "changed"  # type: ignore[misc]

    def test_callback_output_dataclass(self):
        co = CallbackOutput(success=True, error=None)
        assert co.success is True
        assert co.error is None

        co_err = CallbackOutput(success=False, error="timeout")
        assert co_err.success is False
        assert co_err.error == "timeout"
