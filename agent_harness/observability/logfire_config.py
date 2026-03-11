"""logfire configuration — single entry point for observability setup.

Replaces custom logging.py, metrics.py, benchmarks.py with
OpenTelemetry-native distributed tracing via logfire.
"""
from __future__ import annotations

from typing import Any

import logfire


def configure_observability(
    service_name: str = "simuladores",
    environment: str = "development",
    send_to_logfire: bool = False,
    fastapi_app: Any | None = None,
) -> None:
    """Configure logfire for the application."""
    logfire.configure(
        service_name=service_name,
        environment=environment,
        send_to_logfire=send_to_logfire,
    )
    if fastapi_app is not None:
        logfire.instrument_fastapi(fastapi_app)
