"""IDP operativo workflow — Phases 0-6.

Phase 0: Intake (handled by gateway before workflow starts)
Phase 1: Santos writes plan -> PLAN.md
Phase 2: Medina investigates document at document_path
Phase 3: Lamponne executes via discover_api/execute_api
Phase 4: Santos QA review -> qa_report.json
Phase 5: Ravenna synthesizes -> structured_result.json
Phase 6: Post-job learning -> semantic store
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    import os

    from agent_harness.activities.planner import PlannerInput, PlannerOutput
    from agent_harness.activities.agent_loop import AgentLoopInput, AgentLoopOutput
    from agent_harness.activities.investigator import InvestigatorInput, InvestigatorOutput
    from agent_harness.activities.qa_review import QAReviewInput, QAReviewOutput
    from agent_harness.activities.post_job import PostJobInput
    from agent_harness.activities.synthesizer import SynthesizerInput, SynthesizerOutput
    from agent_harness.agents.lamponne import LAMPONNE_TOOLS
    from agent_harness.core.operativo import OperativoStatus
    from agent_harness.domains.idp.operativo import (
        IdpOperativoInput,
        IdpOperativoOutput,
    )


@dataclass(frozen=True)
class IdpWorkflowConfig:
    """Configuration for the IDP workflow."""

    plan_timeout_seconds: int = 120
    investigate_timeout_seconds: int = 120
    execute_timeout_seconds: int = 600
    qa_timeout_seconds: int = 300
    synthesize_timeout_seconds: int = 120
    post_job_timeout_seconds: int = 60
    max_execution_turns: int = 10
    max_correction_attempts: int = 3


@workflow.defn
class IdpOperativoWorkflow:
    """IDP operativo workflow — Phases 0-6.

    Phase 0: Intake (gateway submits workflow)
    Phase 1: Santos writes plan
    Phase 2: Medina investigates document at document_path
    Phase 3: Lamponne executes
    Phase 4: Santos QA review (compare input vs output)
    Phase 5: Ravenna synthesizes (assemble structured_result + QA summary)
    Phase 6: Post-job learning
    """

    def __init__(self, config: IdpWorkflowConfig | None = None) -> None:
        self.config = config or IdpWorkflowConfig()

    def build_plan_input(
        self, operativo_id: str, input: IdpOperativoInput
    ) -> PlannerInput:
        """Phase 1: Build input for Santos planning activity."""
        return PlannerInput(
            operativo_id=operativo_id,
            domain="idp",
            pdf_description=f"Document: {input.document_path}, Plugin: {input.plugin_id}",
        )

    def build_investigate_input(
        self, operativo_id: str, input: IdpOperativoInput
    ) -> InvestigatorInput:
        """Phase 2: Build input for Medina investigation activity.

        IDP now has a document to investigate. Pass the document_path
        and extract the filename for Medina's investigation.
        """
        return InvestigatorInput(
            operativo_id=operativo_id,
            domain="idp",
            pdf_path=input.document_path,
            pdf_filename=os.path.basename(input.document_path),
        )

    def build_execute_input(
        self, operativo_id: str, plan_json: str
    ) -> AgentLoopInput:
        """Phase 3: Build input for Lamponne execution activity."""
        return AgentLoopInput(
            agent_name="lamponne",
            domain="idp",
            operativo_id=operativo_id,
            task_message=f"Execute the following plan:\n\n{plan_json}",
            available_tools=LAMPONNE_TOOLS,
            max_turns=self.config.max_execution_turns,
        )

    def build_qa_input(
        self,
        operativo_id: str,
        input_snapshot_json: str,
        raw_output_json: str,
    ) -> QAReviewInput:
        """Phase 4: Build input for Santos QA review activity."""
        return QAReviewInput(
            operativo_id=operativo_id,
            domain="idp",
            input_snapshot_json=input_snapshot_json,
            raw_output_json=raw_output_json,
            max_correction_attempts=self.config.max_correction_attempts,
        )

    def build_synthesize_input(
        self,
        operativo_id: str,
        progress_entries: str,
        raw_output_json: str,
        qa_report_json: str,
        caller_id: str,
    ) -> SynthesizerInput:
        """Phase 5: Build input for Ravenna synthesis activity."""
        return SynthesizerInput(
            operativo_id=operativo_id,
            domain="idp",
            progress_entries=progress_entries,
            raw_output_json=raw_output_json,
            qa_report_json=qa_report_json,
            caller_id=caller_id,
        )

    def build_post_job_input(
        self, operativo_id: str, session_progress: str
    ) -> PostJobInput:
        """Phase 6: Build input for post-job learning activity."""
        return PostJobInput(
            operativo_id=operativo_id,
            domain="idp",
            session_progress=session_progress,
        )

    def build_output(
        self,
        operativo_id: str,
        final_response: str,
        status: OperativoStatus = OperativoStatus.COMPLETED,
    ) -> IdpOperativoOutput:
        """Build the final output."""
        return IdpOperativoOutput(
            operativo_id=operativo_id,
            status=status,
            structured_result={"response": final_response},
        )

    @workflow.run
    async def run(self, input: IdpOperativoInput) -> IdpOperativoOutput:
        """Execute the full IDP operativo workflow (Phases 1-6)."""
        operativo_id = workflow.info().workflow_id
        progress_entries: list[str] = []

        # Phase 1: Santos plans
        plan_input = self.build_plan_input(operativo_id, input)
        plan_output: PlannerOutput = await workflow.execute_activity(
            "santos_plan",
            plan_input,
            start_to_close_timeout=timedelta(seconds=self.config.plan_timeout_seconds),
        )
        progress_entries.append(f"Phase 1 (Plan): {plan_output.phase_result}")

        # Phase 2: Medina investigates document
        investigate_input = self.build_investigate_input(operativo_id, input)
        investigate_output: InvestigatorOutput = await workflow.execute_activity(
            "medina_investigate",
            investigate_input,
            start_to_close_timeout=timedelta(
                seconds=self.config.investigate_timeout_seconds
            ),
        )
        progress_entries.append(
            f"Phase 2 (Investigate): {investigate_output.phase_result}"
        )

        # Halt if injection detected
        if investigate_output.halted:
            return IdpOperativoOutput(
                operativo_id=operativo_id,
                status=OperativoStatus.NEEDS_REVIEW,
                structured_result={"halted": True, "reason": "injection_detected"},
                qa_summary=f"Halted: injection risk={investigate_output.injection_risk}",
            )

        # Phase 3: Lamponne executes
        execute_input = self.build_execute_input(
            operativo_id, plan_output.plan_json
        )
        execute_output: AgentLoopOutput = await workflow.execute_activity(
            "lamponne_execute",
            execute_input,
            start_to_close_timeout=timedelta(
                seconds=self.config.execute_timeout_seconds
            ),
        )
        progress_entries.append(
            f"Phase 3 (Execute): completed with {len(execute_output.tool_calls_made)} tool calls"
        )

        # Phase 4: Santos QA review with retry loop
        qa_output = await self._qa_with_retry(
            operativo_id=operativo_id,
            input_snapshot_json=investigate_output.input_snapshot_json,
            raw_output_json=execute_output.final_response,
        )
        progress_entries.append(f"Phase 4 (QA): {qa_output.phase_result}")

        # Determine final status from QA
        final_status = (
            OperativoStatus.COMPLETED
            if qa_output.final_status == "COMPLETED"
            else OperativoStatus.NEEDS_REVIEW
        )

        # Phase 5: Ravenna synthesizes
        synthesize_input = self.build_synthesize_input(
            operativo_id=operativo_id,
            progress_entries="\n".join(progress_entries),
            raw_output_json=execute_output.final_response,
            qa_report_json=qa_output.qa_report_json,
            caller_id=input.caller_id,
        )
        synthesize_output: SynthesizerOutput = await workflow.execute_activity(
            "ravenna_synthesize",
            synthesize_input,
            start_to_close_timeout=timedelta(
                seconds=self.config.synthesize_timeout_seconds
            ),
        )
        progress_entries.append(
            f"Phase 5 (Synthesize): {synthesize_output.phase_result}"
        )

        # Phase 6: Post-job learning
        post_job_input = self.build_post_job_input(
            operativo_id=operativo_id,
            session_progress="\n".join(progress_entries),
        )
        await workflow.execute_activity(
            "post_job_learn",
            post_job_input,
            start_to_close_timeout=timedelta(
                seconds=self.config.post_job_timeout_seconds
            ),
        )

        return IdpOperativoOutput(
            operativo_id=operativo_id,
            status=final_status,
            structured_result={
                "response": synthesize_output.structured_result_json,
            },
            extraction_job_id=operativo_id,
            qa_summary=qa_output.qa_report_json,
        )

    async def _qa_with_retry(
        self,
        operativo_id: str,
        input_snapshot_json: str,
        raw_output_json: str,
    ) -> QAReviewOutput:
        """Run QA review with retry loop up to max_correction_attempts.

        Each iteration calls santos_qa_review. If the review passes (COMPLETED),
        return immediately. Otherwise re-execute and re-review up to the limit.
        After exhausting attempts, return the last QA output (NEEDS_REVIEW).
        """
        current_output_json = raw_output_json

        for attempt in range(self.config.max_correction_attempts):
            qa_input = self.build_qa_input(
                operativo_id=operativo_id,
                input_snapshot_json=input_snapshot_json,
                raw_output_json=current_output_json,
            )
            qa_output: QAReviewOutput = await workflow.execute_activity(
                "santos_qa_review",
                qa_input,
                start_to_close_timeout=timedelta(
                    seconds=self.config.qa_timeout_seconds
                ),
            )

            if qa_output.final_status == "COMPLETED":
                return qa_output

            # If not the last attempt, re-execute with corrections
            if attempt < self.config.max_correction_attempts - 1:
                correction_input = self.build_execute_input(
                    operativo_id,
                    f"Apply corrections from QA review:\n\n{qa_output.qa_report_json}",
                )
                correction_output: AgentLoopOutput = await workflow.execute_activity(
                    "lamponne_execute",
                    correction_input,
                    start_to_close_timeout=timedelta(
                        seconds=self.config.execute_timeout_seconds
                    ),
                )
                current_output_json = correction_output.final_response

        return qa_output


# Backwards compatibility alias
IdpWorkflow = IdpOperativoWorkflow
