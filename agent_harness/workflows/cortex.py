"""Cortex Bulletin schedule workflow.

Temporal workflow that periodically generates cross-session memory
bulletins for a domain via the bulletin generator.
"""

from __future__ import annotations

from dataclasses import dataclass

from temporalio import workflow


@dataclass(frozen=True)
class CortexScheduleInput:
    """Input for the Cortex Bulletin schedule workflow."""

    domain: str
    max_patterns: int = 20
    max_tokens: int = 500


@dataclass(frozen=True)
class CortexScheduleOutput:
    """Output from a single Cortex Bulletin generation run."""

    domain: str
    pattern_count: int
    bulletin_summary: str
    generated_at: str  # ISO 8601


@workflow.defn
class CortexBulletinWorkflow:
    """Temporal workflow that generates a Cortex Bulletin for a domain.

    Intended to run on a schedule (e.g. every 60 minutes) via Temporal's
    schedule feature. Each run generates one bulletin and returns the result.
    """

    @workflow.run
    async def run(self, input: CortexScheduleInput) -> CortexScheduleOutput:
        """Generate a single Cortex Bulletin.

        Delegates to the cortex_generate_bulletin activity which handles
        LLM calls and memory store access outside the workflow sandbox.
        """
        from datetime import timedelta

        result = await workflow.execute_activity(
            "cortex_generate_bulletin",
            input,
            start_to_close_timeout=timedelta(seconds=120),
        )

        return CortexScheduleOutput(
            domain=result["domain"],
            pattern_count=result["pattern_count"],
            bulletin_summary=result["bulletin_summary"],
            generated_at=result["generated_at"],
        )
