"""Tests for logfire configuration module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import agent_harness.observability.logfire_config  # noqa: F401 — ensure module is imported before patching


def test_configure_observability_calls_logfire():
    """Verify logfire.configure is called with correct parameters."""
    with patch("agent_harness.observability.logfire_config.logfire") as mock_logfire:
        from agent_harness.observability.logfire_config import configure_observability

        configure_observability(
            service_name="test-service",
            environment="testing",
            send_to_logfire=False,
        )

        mock_logfire.configure.assert_called_once_with(
            service_name="test-service",
            environment="testing",
            send_to_logfire=False,
        )


def test_configure_observability_instruments_fastapi():
    """Verify instrument_fastapi is called when a FastAPI app is provided."""
    with patch("agent_harness.observability.logfire_config.logfire") as mock_logfire:
        from agent_harness.observability.logfire_config import configure_observability

        mock_app = MagicMock()
        configure_observability(
            service_name="test-service",
            environment="testing",
            send_to_logfire=False,
            fastapi_app=mock_app,
        )

        mock_logfire.configure.assert_called_once()
        mock_logfire.instrument_fastapi.assert_called_once_with(mock_app)


def test_configure_without_fastapi_app():
    """Verify instrument_fastapi is NOT called when no app is provided."""
    with patch("agent_harness.observability.logfire_config.logfire") as mock_logfire:
        from agent_harness.observability.logfire_config import configure_observability

        configure_observability(
            service_name="test-service",
            environment="testing",
            send_to_logfire=False,
        )

        mock_logfire.configure.assert_called_once()
        mock_logfire.instrument_fastapi.assert_not_called()
