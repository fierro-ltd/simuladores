"""Callback delivery activity — Temporal activity wrapping CallbackService.

Delivers operativo results to caller-specified callback URLs at the end
of a workflow run. Never fails the workflow — errors are captured in
CallbackOutput.
"""

import json
from dataclasses import dataclass
from typing import Optional

from temporalio import activity


@dataclass(frozen=True)
class CallbackInput:
    """Input for the deliver_callback activity."""

    operativo_id: str
    callback_url: str
    result_json: str  # JSON-encoded result dict


@dataclass(frozen=True)
class CallbackOutput:
    """Output from the deliver_callback activity."""

    success: bool
    error: Optional[str] = None


@activity.defn
async def deliver_callback(input: CallbackInput) -> CallbackOutput:
    """Deliver operativo result to the caller's callback URL.

    Wraps CallbackService. Never raises — captures all errors in the output.
    """
    try:
        result_dict = json.loads(input.result_json)
    except (json.JSONDecodeError, TypeError) as exc:
        return CallbackOutput(success=False, error=f"Invalid result_json: {exc}")

    # Lazy import to avoid circular dependency:
    # callback -> gateway.callback -> gateway.__init__ -> gateway.app -> workers.dce
    # -> workflows.operativo_workflow -> callback
    from agent_harness.gateway.callback import CallbackService

    service = CallbackService()
    cb_result = await service.deliver(
        url=input.callback_url,
        operativo_id=input.operativo_id,
        result=result_dict,
    )

    return CallbackOutput(
        success=cb_result.success,
        error=cb_result.error,
    )
