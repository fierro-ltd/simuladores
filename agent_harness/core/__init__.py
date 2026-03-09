"""Core types for the Agent Harness."""

from agent_harness.core.errors import (
    ErrorCode,
    ErrorResponse,
    HarnessError,
)
from agent_harness.core.operativo import (
    OperativoResult,
    OperativoStatus,
    Phase,
    QAIssue,
    Severity,
)
from agent_harness.core.permissions import (
    GLOBAL_DENY_LIST,
    SANDBOX_TOOLS,
    PermissionLevel,
    PolicyChain,
    PolicyResult,
    ToolDeniedError,
    ToolPolicy,
)
from agent_harness.core.plan import (
    AgentTask,
    ExecutionPlan,
    PhaseResult,
)
from agent_harness.core.registry import (
    OperativoRegistry,
    RegistryEntry,
)

__all__ = [
    # errors
    "ErrorCode",
    "ErrorResponse",
    "HarnessError",
    # operativo
    "Phase",
    "OperativoStatus",
    "Severity",
    "QAIssue",
    "OperativoResult",
    # plan
    "AgentTask",
    "ExecutionPlan",
    "PhaseResult",
    # permissions
    "GLOBAL_DENY_LIST",
    "SANDBOX_TOOLS",
    "PermissionLevel",
    "ToolDeniedError",
    "PolicyResult",
    "ToolPolicy",
    "PolicyChain",
    # registry
    "RegistryEntry",
    "OperativoRegistry",
]
