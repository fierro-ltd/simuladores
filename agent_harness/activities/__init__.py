"""Temporal activities."""

from agent_harness.activities.planner import PlannerInput, PlannerOutput
from agent_harness.activities.agent_loop import AgentLoopInput, AgentLoopOutput
from agent_harness.activities.tool_executor import ToolExecutor
from agent_harness.activities.investigator import (
    InvestigatorInput,
    InvestigatorOutput,
    InputSnapshot,
)
from agent_harness.activities.qa_review import QAReviewInput, QAReviewOutput
from agent_harness.activities.post_job import PostJobInput, PostJobOutput
from agent_harness.activities.synthesizer import (
    SynthesizerInput,
    SynthesizerOutput,
    QASummary,
)
from agent_harness.activities.web_verify import WebVerifyInput, WebVerifyOutput
from agent_harness.activities.factory import (
    get_anthropic_client,
    build_tool_handler,
    load_domain_memory,
)

__all__ = [
    "AgentLoopInput",
    "AgentLoopOutput",
    "CallbackInput",
    "CallbackOutput",
    "InputSnapshot",
    "InvestigatorInput",
    "InvestigatorOutput",
    "PlannerInput",
    "PlannerOutput",
    "PostJobInput",
    "PostJobOutput",
    "QAReviewInput",
    "QAReviewOutput",
    "QASummary",
    "SynthesizerInput",
    "SynthesizerOutput",
    "ToolExecutor",
    "WebVerifyInput",
    "WebVerifyOutput",
    # Factory helpers
    "get_anthropic_client",
    "build_tool_handler",
    "load_domain_memory",
    # Activity implementations (import from .implementations directly to avoid circular imports)
    "santos_plan",
    "medina_investigate",
    "lamponne_execute",
    "santos_qa_review",
    "ravenna_synthesize",
    "cpc_web_verify",
    "post_job_learn",
    "deliver_callback",
]


def __getattr__(name: str):
    """Lazy imports for activity implementations to avoid circular imports."""
    _impl_names = {
        "santos_plan",
        "medina_investigate",
        "lamponne_execute",
        "santos_qa_review",
        "ravenna_synthesize",
        "cpc_web_verify",
        "post_job_learn",
    }
    if name in _impl_names:
        from agent_harness.activities import implementations as _impl

        return getattr(_impl, name)
    # Callback activity and dataclasses — lazy to avoid circular imports
    _callback_names = {"deliver_callback", "CallbackInput", "CallbackOutput"}
    if name in _callback_names:
        from agent_harness.activities import callback as _cb

        return getattr(_cb, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
