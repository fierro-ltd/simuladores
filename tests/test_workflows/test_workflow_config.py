"""Tests for workflow configuration."""

from agent_harness.workflows.operativo_workflow import (
    E2E_FAST_WORKFLOW_CONFIG,
    WorkflowConfig,
)


def test_e2e_fast_timeouts_sufficient_for_dce_backend():
    """DCE Backend can take ~3 min, so investigate/QA timeouts must be >= 300s."""
    assert E2E_FAST_WORKFLOW_CONFIG.investigate_timeout_seconds >= 300
    assert E2E_FAST_WORKFLOW_CONFIG.qa_timeout_seconds >= 300


def test_default_config_has_generous_timeouts():
    """Default production config should have 30-min timeouts."""
    cfg = WorkflowConfig()
    assert cfg.investigate_timeout_seconds == 1800
    assert cfg.qa_timeout_seconds == 1800


def test_e2e_fast_has_reduced_retries():
    """E2E fast mode should limit correction attempts."""
    assert E2E_FAST_WORKFLOW_CONFIG.max_correction_attempts == 1
    assert E2E_FAST_WORKFLOW_CONFIG.max_execution_turns == 3
