"""Tests for parallel Phase 2a/2b in DCE workflow."""


import pytest

from agent_harness.workflows.operativo_workflow import (
    CPCOperativoWorkflow,
    WorkflowConfig,
)
from agent_harness.activities.vision_extract import VisionExtractInput
from agent_harness.activities.qa_review import QAReviewInput
from agent_harness.domains.dce.operativo import CPCOperativoInput


class TestWorkflowConfigVision:
    """Tests for vision timeout in WorkflowConfig."""

    def test_default_vision_timeout(self):
        config = WorkflowConfig()
        assert config.vision_timeout_seconds == 600

    def test_custom_vision_timeout(self):
        config = WorkflowConfig(vision_timeout_seconds=900)
        assert config.vision_timeout_seconds == 900

    def test_existing_defaults_unchanged(self):
        config = WorkflowConfig()
        assert config.plan_timeout_seconds == 1800
        assert config.investigate_timeout_seconds == 1800
        assert config.execute_timeout_seconds == 1800
        assert config.qa_timeout_seconds == 1800


class TestBuildVisionExtractInput:
    """Tests for build_vision_extract_input method."""

    def test_builds_correct_input(self):
        wf = CPCOperativoWorkflow()
        mock_input = CPCOperativoInput(
            pdf_path="/tmp/test.pdf",
            pdf_filename="test.pdf",
            caller_id="test-caller",
        )
        result = wf.build_vision_extract_input("op-1", mock_input)
        assert isinstance(result, VisionExtractInput)
        assert result.operativo_id == "op-1"
        assert result.domain == "dce"
        assert result.pdf_path == "/tmp/test.pdf"
        assert result.pdf_filename == "test.pdf"

    def test_default_max_pages(self):
        wf = CPCOperativoWorkflow()
        mock_input = CPCOperativoInput(
            pdf_path="/tmp/test.pdf",
            pdf_filename="test.pdf",
            caller_id="test-caller",
        )
        result = wf.build_vision_extract_input("op-1", mock_input)
        assert result.max_pages == 20


class TestBuildQAInputWithVision:
    """Tests for QA input now including vision extraction."""

    def test_qa_input_includes_vision(self):
        wf = CPCOperativoWorkflow()
        result = wf.build_qa_input(
            operativo_id="op-1",
            input_snapshot_json='{"fields": "medina"}',
            raw_output_json='{"output": "lamponne"}',
            vision_extraction_json='{"fields": "gemini"}',
        )
        assert isinstance(result, QAReviewInput)
        assert result.vision_extraction_json == '{"fields": "gemini"}'

    def test_qa_input_vision_defaults_empty(self):
        wf = CPCOperativoWorkflow()
        result = wf.build_qa_input(
            operativo_id="op-1",
            input_snapshot_json="{}",
            raw_output_json="{}",
        )
        assert result.vision_extraction_json == ""

    def test_qa_input_preserves_other_fields(self):
        wf = CPCOperativoWorkflow()
        result = wf.build_qa_input(
            operativo_id="op-1",
            input_snapshot_json='{"a": 1}',
            raw_output_json='{"b": 2}',
            vision_extraction_json='{"c": 3}',
        )
        assert result.input_snapshot_json == '{"a": 1}'
        assert result.raw_output_json == '{"b": 2}'
        assert result.domain == "dce"


class TestVisionExtractInputDataclass:
    """Tests for VisionExtractInput dataclass."""

    def test_frozen(self):
        inp = VisionExtractInput(
            operativo_id="op-1",
            domain="dce",
            pdf_path="/tmp/test.pdf",
            pdf_filename="test.pdf",
        )
        with pytest.raises(AttributeError):
            inp.domain = "has"

    def test_default_max_pages(self):
        inp = VisionExtractInput(
            operativo_id="op-1",
            domain="dce",
            pdf_path="/tmp/test.pdf",
            pdf_filename="test.pdf",
        )
        assert inp.max_pages == 20

    def test_custom_max_pages(self):
        inp = VisionExtractInput(
            operativo_id="op-1",
            domain="dce",
            pdf_path="/tmp/test.pdf",
            pdf_filename="test.pdf",
            max_pages=5,
        )
        assert inp.max_pages == 5
