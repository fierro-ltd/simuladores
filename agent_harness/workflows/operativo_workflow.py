"""DCE operativo workflow — Phases 0-6.

Phase 0: Intake (handled by gateway before workflow starts)
Phase 1: Santos writes plan -> PLAN.md
Phase 2a: Medina investigates -> input_snapshot.json
Phase 2b: Gemini vision extraction (parallel with 2a)
Phase 3: Lamponne executes via discover_api/execute_api
Phase 4: Santos QA review -> qa_report.json (cross-references vision)
Phase 5: Ravenna synthesizes -> structured_result.json
Phase 6: Post-job learning -> semantic store
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from agent_harness.activities.callback import CallbackInput, CallbackOutput
    from agent_harness.domains.dce.citation_completeness import compute_completeness_report
    from agent_harness.activities.planner import PlannerInput, PlannerOutput
    from agent_harness.activities.agent_loop import AgentLoopInput, AgentLoopOutput
    from agent_harness.activities.investigator import InvestigatorInput, InvestigatorOutput
    from agent_harness.activities.qa_review import QAReviewInput, QAReviewOutput
    from agent_harness.activities.post_job import PostJobInput, PostJobOutput
    from agent_harness.activities.synthesizer import SynthesizerInput, SynthesizerOutput
    from agent_harness.activities.web_verify import WebVerifyInput, WebVerifyOutput
    from agent_harness.activities.vision_extract import VisionExtractInput, VisionExtractOutput
    from agent_harness.agents.lamponne import LAMPONNE_TOOLS
    from agent_harness.core.operativo import OperativoStatus
    from agent_harness.domains.dce.operativo import CPCOperativoInput, CPCOperativoOutput


_NO_RETRY = RetryPolicy(maximum_attempts=1)


@dataclass(frozen=True)
class WorkflowConfig:
    """Configuration for the DCE workflow."""
    plan_timeout_seconds: int = 1800
    investigate_timeout_seconds: int = 1800
    vision_timeout_seconds: int = 600
    execute_timeout_seconds: int = 1800
    qa_timeout_seconds: int = 1800
    synthesize_timeout_seconds: int = 1800
    post_job_timeout_seconds: int = 300
    max_execution_turns: int = 10
    max_correction_attempts: int = 3


E2E_FAST_WORKFLOW_CONFIG = WorkflowConfig(
    plan_timeout_seconds=120,
    investigate_timeout_seconds=300,   # DCE Backend needs ~3 min per PDF
    vision_timeout_seconds=120,
    execute_timeout_seconds=300,
    qa_timeout_seconds=300,            # Santos-QA with citation review is heavier
    synthesize_timeout_seconds=120,
    post_job_timeout_seconds=60,
    max_execution_turns=3,
    max_correction_attempts=1,
)


@workflow.defn
class CPCOperativoWorkflow:
    """DCE operativo workflow — Phases 0-6.

    Phase 0: Intake (gateway submits workflow)
    Phase 1: Santos writes plan
    Phase 2a: Medina investigates (injection scan + field extraction)
    Phase 2b: Gemini vision extraction (parallel with 2a)
    Phase 3: Lamponne executes
    Phase 4: Santos QA review (cross-references DCE Backend, vision, Lamponne)
    Phase 5: Ravenna synthesizes (assemble structured_result + QA summary)
    Phase 6: Post-job learning
    """

    def __init__(self, config: WorkflowConfig | None = None) -> None:
        self.config = config or WorkflowConfig()

    @staticmethod
    def _config_for_input(input: CPCOperativoInput, default_config: WorkflowConfig) -> WorkflowConfig:
        """Return per-run workflow config (production default or e2e fast mode)."""
        return E2E_FAST_WORKFLOW_CONFIG if input.e2e_fast_mode else default_config

    @staticmethod
    def _has_retryable_blocking_issues(qa_report_json: str) -> bool:
        """Return True only when blocking issues include auto-correctable checks."""
        try:
            qa_obj = json.loads(qa_report_json)
        except Exception:
            # Preserve current behavior if report is unparsable.
            return True
        checks = qa_obj.get("checks", []) if isinstance(qa_obj, dict) else []
        if not isinstance(checks, list):
            return True
        blocking_checks = [
            item
            for item in checks
            if isinstance(item, dict) and str(item.get("severity", "")).upper() == "BLOCKING"
        ]
        if not blocking_checks:
            return False
        return any(bool(item.get("auto_correctable", False)) for item in blocking_checks)

    def build_plan_input(self, operativo_id: str, input: CPCOperativoInput) -> PlannerInput:
        """Phase 1: Build input for Santos planning activity."""
        return PlannerInput(
            operativo_id=operativo_id,
            domain="dce",
            pdf_description=f"DCE PDF: {input.pdf_filename}",
        )

    def build_investigate_input(
        self, operativo_id: str, input: CPCOperativoInput
    ) -> InvestigatorInput:
        """Phase 2a: Build input for Medina investigation activity."""
        return InvestigatorInput(
            operativo_id=operativo_id,
            domain="dce",
            pdf_path=input.pdf_path,
            pdf_filename=input.pdf_filename,
        )

    def build_vision_extract_input(
        self, operativo_id: str, input: CPCOperativoInput
    ) -> VisionExtractInput:
        """Phase 2b: Build input for Gemini vision extraction activity."""
        return VisionExtractInput(
            operativo_id=operativo_id,
            domain="dce",
            pdf_path=input.pdf_path,
            pdf_filename=input.pdf_filename,
        )

    def build_execute_input(
        self, operativo_id: str, plan_json: str, runtime_config: WorkflowConfig | None = None
    ) -> AgentLoopInput:
        """Phase 3: Build input for Lamponne execution activity."""
        cfg = runtime_config or self.config
        return AgentLoopInput(
            agent_name="lamponne",
            domain="dce",
            operativo_id=operativo_id,
            task_message=f"Execute the following plan:\n\n{plan_json}",
            available_tools=[t["name"] for t in LAMPONNE_TOOLS],
            max_turns=cfg.max_execution_turns,
        )

    def build_qa_input(
        self,
        operativo_id: str,
        input_snapshot_json: str,
        raw_output_json: str,
        vision_extraction_json: str = "",
        citation_completeness_report_json: str = "",
        web_verification_evidence_json: str = "",
        runtime_config: WorkflowConfig | None = None,
    ) -> QAReviewInput:
        """Phase 4: Build input for Santos QA review activity."""
        cfg = runtime_config or self.config
        return QAReviewInput(
            operativo_id=operativo_id,
            domain="dce",
            input_snapshot_json=input_snapshot_json,
            raw_output_json=raw_output_json,
            max_correction_attempts=cfg.max_correction_attempts,
            vision_extraction_json=vision_extraction_json,
            citation_completeness_report_json=citation_completeness_report_json,
            web_verification_evidence_json=web_verification_evidence_json,
        )

    def build_synthesize_input(
        self,
        operativo_id: str,
        progress_entries: str,
        raw_output_json: str,
        qa_report_json: str,
        caller_id: str,
        corrected_citation_matrix_json: str = "",
        citation_completeness_report_json: str = "",
        web_verification_evidence_json: str = "",
    ) -> SynthesizerInput:
        """Phase 5: Build input for Ravenna synthesis activity."""
        return SynthesizerInput(
            operativo_id=operativo_id,
            domain="dce",
            progress_entries=progress_entries,
            raw_output_json=raw_output_json,
            qa_report_json=qa_report_json,
            caller_id=caller_id,
            corrected_citation_matrix_json=corrected_citation_matrix_json,
            citation_completeness_report_json=citation_completeness_report_json,
            web_verification_evidence_json=web_verification_evidence_json,
        )

    def build_post_job_input(
        self, operativo_id: str, session_progress: str
    ) -> PostJobInput:
        """Phase 6: Build input for post-job learning activity."""
        return PostJobInput(
            operativo_id=operativo_id,
            domain="dce",
            session_progress=session_progress,
        )

    def build_output(
        self,
        operativo_id: str,
        final_response: str,
        status: OperativoStatus = OperativoStatus.COMPLETED,
    ) -> CPCOperativoOutput:
        """Build the final output."""
        return CPCOperativoOutput(
            operativo_id=operativo_id,
            status=status,
            structured_result={"response": final_response},
        )

    @workflow.run
    async def run(self, input: CPCOperativoInput) -> CPCOperativoOutput:
        """Execute the full DCE operativo workflow (Phases 1-6)."""
        operativo_id = workflow.info().workflow_id
        runtime_config = self._config_for_input(input, self.config)
        progress_entries: list[str] = []

        # Phase 1: Santos plans
        plan_input = self.build_plan_input(operativo_id, input)
        plan_output: PlannerOutput = await workflow.execute_activity(
            "santos_plan",
            plan_input,
            result_type=PlannerOutput,
            start_to_close_timeout=timedelta(seconds=runtime_config.plan_timeout_seconds),
            retry_policy=_NO_RETRY,
        )
        progress_entries.append(f"Phase 1 (Plan): {plan_output.phase_result}")

        # Phase 2a + 2b: Medina investigates and Gemini vision extract in parallel
        investigate_input = self.build_investigate_input(operativo_id, input)
        vision_input = self.build_vision_extract_input(operativo_id, input)

        investigate_task = workflow.execute_activity(
            "medina_investigate",
            investigate_input,
            result_type=InvestigatorOutput,
            start_to_close_timeout=timedelta(seconds=runtime_config.investigate_timeout_seconds),
            retry_policy=_NO_RETRY,
        )
        vision_task = workflow.execute_activity(
            "gemini_vision_extract",
            vision_input,
            result_type=VisionExtractOutput,
            start_to_close_timeout=timedelta(seconds=runtime_config.vision_timeout_seconds),
            retry_policy=_NO_RETRY,
        )

        # Wait for both to complete
        investigate_output, vision_output = await asyncio.gather(
            investigate_task, vision_task
        )
        progress_entries.append(f"Phase 2a (Investigate): {investigate_output.phase_result}")
        progress_entries.append(
            f"Phase 2b (Vision): extracted {vision_output.pages_extracted} pages "
            f"via {vision_output.source}"
        )

        # Halt if injection detected
        if investigate_output.halted:
            return CPCOperativoOutput(
                operativo_id=operativo_id,
                status=OperativoStatus.NEEDS_REVIEW,
                structured_result={"halted": True, "reason": "injection_detected"},
                qa_summary=f"Halted: injection risk={investigate_output.injection_risk}",
            )

        # Phase 3: Lamponne executes
        execute_input = self.build_execute_input(
            operativo_id, plan_output.plan_json, runtime_config
        )
        execute_output: AgentLoopOutput = await workflow.execute_activity(
            "lamponne_execute",
            execute_input,
            result_type=AgentLoopOutput,
            start_to_close_timeout=timedelta(seconds=runtime_config.execute_timeout_seconds),
            retry_policy=_NO_RETRY,
        )
        progress_entries.append(f"Phase 3 (Execute): completed with {len(execute_output.tool_calls_made)} tool calls")

        # Only pass vision data to QA if extraction produced meaningful fields
        vision_json = vision_output.structured_fields if vision_output.pages_extracted > 0 else ""

        # Compute citation completeness report (DCE) after Medina extraction is available
        citation_report = compute_completeness_report(
            investigate_output.input_snapshot_json,
            vision_extraction_json=vision_json,
        )
        web_verification_evidence_json = ""
        try:
            report_obj = json.loads(citation_report)
        except Exception:
            report_obj = {}
        if isinstance(report_obj, dict) and report_obj.get("web_verification_recommended"):
            verify_input = WebVerifyInput(
                operativo_id=operativo_id,
                domain="dce",
                citation_completeness_report_json=citation_report,
            )
            verify_output: WebVerifyOutput = await workflow.execute_activity(
                "cpc_web_verify",
                verify_input,
                result_type=WebVerifyOutput,
                start_to_close_timeout=timedelta(seconds=runtime_config.qa_timeout_seconds),
                retry_policy=_NO_RETRY,
            )
            web_verification_evidence_json = verify_output.verification_json

        # Phase 4: Santos QA review with retry loop
        qa_output = await self._qa_with_retry(
            operativo_id=operativo_id,
            input_snapshot_json=investigate_output.input_snapshot_json,
            raw_output_json=execute_output.final_response,
            vision_extraction_json=vision_json,
            citation_completeness_report_json=citation_report,
            web_verification_evidence_json=web_verification_evidence_json,
            runtime_config=runtime_config,
        )
        progress_entries.append(f"Phase 4 (QA): {qa_output.phase_result}")

        # Determine final status from QA
        final_status = (
            OperativoStatus.COMPLETED
            if qa_output.final_status == "COMPLETED"
            else OperativoStatus.NEEDS_REVIEW
        )

        # Phase 5: Ravenna synthesizes (include citation report for web_verification_recommended)
        synthesize_input = self.build_synthesize_input(
            operativo_id=operativo_id,
            progress_entries="\n".join(progress_entries),
            raw_output_json=execute_output.final_response,
            qa_report_json=qa_output.qa_report_json,
            caller_id=input.caller_id,
            corrected_citation_matrix_json=qa_output.corrected_citation_matrix_json,
            citation_completeness_report_json=citation_report,
            web_verification_evidence_json=web_verification_evidence_json,
        )
        synthesize_output: SynthesizerOutput = await workflow.execute_activity(
            "ravenna_synthesize",
            synthesize_input,
            result_type=SynthesizerOutput,
            start_to_close_timeout=timedelta(seconds=runtime_config.synthesize_timeout_seconds),
            retry_policy=_NO_RETRY,
        )
        progress_entries.append(f"Phase 5 (Synthesize): {synthesize_output.phase_result}")

        # Callback delivery (if requested)
        if input.callback_url:
            callback_input = CallbackInput(
                operativo_id=operativo_id,
                callback_url=input.callback_url,
                result_json=synthesize_output.structured_result_json,
            )
            await workflow.execute_activity(
                "deliver_callback",
                callback_input,
                result_type=CallbackOutput,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=_NO_RETRY,
            )

        # Phase 6: Post-job learning
        if not input.e2e_fast_mode:
            post_job_input = self.build_post_job_input(
                operativo_id=operativo_id,
                session_progress="\n".join(progress_entries),
            )
            await workflow.execute_activity(
                "post_job_learn",
                post_job_input,
                result_type=PostJobOutput,
                start_to_close_timeout=timedelta(seconds=runtime_config.post_job_timeout_seconds),
                retry_policy=_NO_RETRY,
            )

        return CPCOperativoOutput(
            operativo_id=operativo_id,
            status=final_status,
            structured_result={"response": synthesize_output.structured_result_json},
            report_url=synthesize_output.report_url,
            qa_summary=qa_output.qa_report_json,
        )

    async def _qa_with_retry(
        self,
        operativo_id: str,
        input_snapshot_json: str,
        raw_output_json: str,
        vision_extraction_json: str = "",
        citation_completeness_report_json: str = "",
        web_verification_evidence_json: str = "",
        runtime_config: WorkflowConfig | None = None,
    ) -> QAReviewOutput:
        """Run QA review with retry loop up to max_correction_attempts.

        Each iteration calls santos_qa_review. If the review passes (COMPLETED),
        return immediately. Otherwise re-execute and re-review up to the limit.
        After exhausting attempts, return the last QA output (NEEDS_REVIEW).
        """
        current_output_json = raw_output_json
        cfg = runtime_config or self.config

        for attempt in range(cfg.max_correction_attempts):
            qa_input = self.build_qa_input(
                operativo_id=operativo_id,
                input_snapshot_json=input_snapshot_json,
                raw_output_json=current_output_json,
                vision_extraction_json=vision_extraction_json,
                citation_completeness_report_json=citation_completeness_report_json,
                web_verification_evidence_json=web_verification_evidence_json,
                runtime_config=cfg,
            )
            qa_output: QAReviewOutput = await workflow.execute_activity(
                "santos_qa_review",
                qa_input,
                result_type=QAReviewOutput,
                start_to_close_timeout=timedelta(seconds=cfg.qa_timeout_seconds),
                retry_policy=_NO_RETRY,
            )

            if qa_output.final_status == "COMPLETED":
                return qa_output

            # If not the last attempt and we have auto-correctable blocking issues,
            # re-execute with corrections.
            if (
                attempt < cfg.max_correction_attempts - 1
                and self._has_retryable_blocking_issues(qa_output.qa_report_json)
            ):
                correction_input = self.build_execute_input(
                    operativo_id,
                    f"Apply corrections from QA review:\n\n{qa_output.qa_report_json}",
                    cfg,
                )
                correction_output: AgentLoopOutput = await workflow.execute_activity(
                    "lamponne_execute",
                    correction_input,
                    result_type=AgentLoopOutput,
                    start_to_close_timeout=timedelta(seconds=cfg.execute_timeout_seconds),
                    retry_policy=_NO_RETRY,
                )
                current_output_json = correction_output.final_response

        return qa_output


# Backwards compatibility alias
CPCWorkflow = CPCOperativoWorkflow
