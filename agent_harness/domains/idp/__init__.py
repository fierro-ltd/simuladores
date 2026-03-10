"""Intelligent Document Processing domain."""

from agent_harness.domains.idp.operativo import (
    IdpOperativoInput,
    IdpOperativoOutput,
)
from agent_harness.domains.idp.tools import (
    discover_api,
    get_operation_schema,
    list_operations,
)

__all__ = [
    "IdpOperativoInput",
    "IdpOperativoOutput",
    "discover_api",
    "get_operation_schema",
    "list_operations",
]
