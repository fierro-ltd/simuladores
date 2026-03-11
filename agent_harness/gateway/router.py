"""Domain router — routes operativo requests by domain classification."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from agent_harness.core.operativo import OperativoStatus
from agent_harness.core.registry import OperativoRegistry


@dataclass(frozen=True)
class RouteResult:
    """Result of routing an operativo request."""
    operativo_id: str
    domain: str
    task_queue: str
    workflow_name: str
    status: OperativoStatus = OperativoStatus.PENDING


class RouteError(Exception):
    """Raised when routing fails."""


def build_default_registry() -> OperativoRegistry:
    """Build the default registry with all known domains."""
    registry = OperativoRegistry()
    registry.register("dce", "dce-operativo", "CPCWorkflow")
    registry.register("has", "has-operativo", "CEEWorkflow")
    registry.register("idp", "idp-operativo", "IdpWorkflow")
    return registry


def route_operativo(
    domain: str,
    registry: OperativoRegistry | None = None,
) -> RouteResult:
    """Route an operativo request to the correct workflow.

    Raises RouteError if the domain is not registered.
    """
    if not domain:
        raise RouteError("domain is required")

    reg = registry or build_default_registry()
    try:
        entry = reg.get(domain)
    except KeyError:
        raise RouteError(f"Unknown domain: '{domain}'") from None

    operativo_id = f"{domain}-{uuid.uuid4().hex[:12]}"
    return RouteResult(
        operativo_id=operativo_id,
        domain=entry.domain,
        task_queue=entry.task_queue,
        workflow_name=entry.workflow_name,
    )
