"""IDP domain operativo input and output types."""

from __future__ import annotations

from dataclasses import dataclass

from agent_harness.core.operativo import OperativoStatus


@dataclass(frozen=True)
class IdpOperativoInput:
    """Input for an IDP operativo execution."""

    product_description: str
    caller_id: str
    target_markets: list[str] | None = None  # ["US", "EU", ...]
    product_category: str | None = None
    callback_url: str | None = None


@dataclass(frozen=True)
class IdpOperativoOutput:
    """Output from an IDP operativo execution."""

    operativo_id: str
    status: OperativoStatus
    structured_result: dict
    test_plan_url: str | None = None
    qa_summary: str | None = None
