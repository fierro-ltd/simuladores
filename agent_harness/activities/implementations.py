"""Temporal activity implementations for all 6 phases.

Each activity:
1. Gets AnthropicClient via get_anthropic_client()
2. Gets StorageBackend via _get_storage_backend()
3. Loads domain memory via load_domain_memory()
4. Constructs the appropriate agent
5. Calls the agent executor method
6. Returns the activity output dataclass
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict

from temporalio import activity

from typing import Any

from agent_harness.activities.agent_loop import AgentLoopInput, AgentLoopOutput
from agent_harness.activities.factory import (
    build_tool_handler,
    get_anthropic_client,
    get_bulletin_store,
    get_cache_monitor,
    get_memory_recall,
    load_domain_memory,
)
from agent_harness.memory.bulletin import BulletinConfig, generate_bulletin
from agent_harness.workflows.cortex import CortexScheduleInput
from agent_harness.activities.investigator import InvestigatorInput, InvestigatorOutput
from agent_harness.activities.planner import PlannerInput, PlannerOutput
from agent_harness.activities.post_job import PostJobInput, PostJobOutput, extract_patterns
from agent_harness.memory.embeddings import FakeEmbeddingClient
from agent_harness.memory.graph_store import InMemoryGraphStore
from agent_harness.activities.qa_review import QAReviewInput, QAReviewOutput
from agent_harness.activities.synthesizer import SynthesizerInput, SynthesizerOutput
from agent_harness.activities.web_verify import WebVerifyInput, WebVerifyOutput
from agent_harness.activities.vision_extract import (
    VisionExtractInput,
    VisionExtractOutput,
    gemini_vision_extract,
)
from agent_harness.agents.base import AGENT_MODELS, AgentConfig, BaseAgent
from agent_harness.agents.lamponne import LamponneExecutor
from agent_harness.agents.medina import MedinaInvestigator
from agent_harness.agents.qa_reviewer import SantosQAReviewer
from agent_harness.agents.ravenna import RavennaSynthesizer
from agent_harness.agents.santos import SANTOS_SYSTEM_IDENTITY, SantosPlanner
from agent_harness.domains.dce.checklist import CPC_VERIFICATION_CHECKLIST
from agent_harness.storage.local import LocalStorageBackend

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.DOTALL)
_DOMAIN_MEMORY_CACHE: dict[str, str] = {}


def _build_web_verification_queries(citation_report_json: str, max_queries: int = 4) -> list[str]:
    """Build focused web-verification queries from citation completeness report."""
    report = _safe_json_loads(citation_report_json)
    if not isinstance(report, dict):
        return []

    queries: list[str] = []
    invalid = report.get("invalid_citations", [])
    if isinstance(invalid, list):
        for item in invalid:
            citation = ""
            if isinstance(item, dict):
                citation = str(item.get("citation", "")).strip()
            elif isinstance(item, str):
                citation = item.strip()
            if citation:
                queries.append(
                    f'compliance citation applicability "{citation}" official source site:cpsc.gov OR site:ecfr.gov'
                )

    missing = report.get("missing_citations", [])
    if isinstance(missing, list):
        for citation in missing:
            c = str(citation).strip()
            if c:
                queries.append(
                    f'compliance children product certificate required citation "{c}" site:cpsc.gov OR site:ecfr.gov'
                )

    # Dedupe while preserving order
    deduped: list[str] = []
    seen: set[str] = set()
    for q in queries:
        if q not in seen:
            seen.add(q)
            deduped.append(q)
    return deduped[:max_queries]


def _safe_json_loads(value: str) -> Any | None:
    """Parse JSON text and return None on errors."""
    try:
        return json.loads(value)
    except Exception:
        return None


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Extract a JSON object from free-form model output."""
    parsed = _safe_json_loads(text)
    if isinstance(parsed, dict):
        return parsed

    match = _JSON_FENCE_RE.search(text)
    if match:
        parsed = _safe_json_loads(match.group(1).strip())
        if isinstance(parsed, dict):
            return parsed
    return None


def _qa_summary_from_report(qa_report_json: str) -> dict[str, int]:
    """Build deterministic QA summary counts from qa_report_json."""
    qa_obj = _safe_json_loads(qa_report_json)
    checks = qa_obj.get("checks", []) if isinstance(qa_obj, dict) else []
    if not isinstance(checks, list):
        checks = []

    blocking = 0
    warnings = 0
    info = 0
    for check in checks:
        if not isinstance(check, dict):
            continue
        severity = str(check.get("severity", "")).upper()
        if severity == "BLOCKING":
            blocking += 1
        elif severity == "WARNING":
            warnings += 1
        else:
            info += 1
    corrections_applied = int(qa_obj.get("correction_attempts", 0)) if isinstance(qa_obj, dict) else 0
    return {
        "total_checks": len(checks),
        "blocking": blocking,
        "warnings": warnings,
        "info": info,
        "corrections_applied": corrections_applied,
    }


def _normalize_structured_result_json(
    *,
    operativo_id: str,
    domain: str,
    raw_output_json: str,
    qa_report_json: str,
    synthesized_text: str,
    corrected_citation_matrix_json: str = "",
    citation_completeness_report_json: str = "",
    web_verification_evidence_json: str = "",
) -> str:
    """Return guaranteed-valid structured_result JSON string."""
    qa_summary = _qa_summary_from_report(qa_report_json)
    parsed = _extract_json_object(synthesized_text)

    if parsed is None:
        raw_result = _safe_json_loads(raw_output_json)
        result_obj = raw_result if isinstance(raw_result, dict) else {"raw_output": raw_output_json}
        parsed = {
            "operativo_id": operativo_id,
            "status": "NEEDS_REVIEW" if qa_summary["blocking"] > 0 else "COMPLETED",
            "domain": domain,
            "result": result_obj,
            "qa_summary": qa_summary,
            "report_url": f"/reports/{operativo_id}/structured_result.json",
            "metadata": {
                "duration_seconds": 0,
                "phases_completed": 6,
                "agents_invoked": [
                    "santos",
                    "medina",
                    "lamponne",
                    "santos",
                    "ravenna",
                ],
                "fallback_used": True,
                "fallback_reason": "ravenna_output_not_json",
            },
        }

    parsed["operativo_id"] = parsed.get("operativo_id", operativo_id)
    parsed["domain"] = parsed.get("domain", domain)
    parsed["report_url"] = parsed.get("report_url", f"/reports/{operativo_id}/structured_result.json")
    if not isinstance(parsed.get("qa_summary"), dict):
        parsed["qa_summary"] = qa_summary

    if corrected_citation_matrix_json:
        try:
            parsed["corrected_citation_matrix"] = json.loads(corrected_citation_matrix_json)
        except json.JSONDecodeError:
            parsed["corrected_citation_matrix"] = []

    # Add web_verification_recommended from citation completeness report when ambiguity present
    if citation_completeness_report_json:
        try:
            ccr = json.loads(citation_completeness_report_json)
            if isinstance(ccr, dict) and ccr.get("web_verification_recommended"):
                parsed["web_verification_recommended"] = True
        except json.JSONDecodeError:
            pass

    if web_verification_evidence_json:
        try:
            wv = json.loads(web_verification_evidence_json)
            if isinstance(wv, dict) and wv.get("results"):
                parsed["web_verification_evidence"] = wv
        except json.JSONDecodeError:
            pass

    return json.dumps(parsed, default=str)


async def _retrieve_semantic_patterns(domain: str, query: str) -> list[str]:
    """Retrieve combined semantic patterns from memory recall and bulletin store.

    Merges patterns from the graph-based MemoryRecall (similarity search)
    with bulletin patterns (cross-session summaries) for PromptBuilder L3.
    """
    recall = get_memory_recall()
    bulletin_store = get_bulletin_store()

    patterns = await recall.retrieve_patterns(domain, query, top_k=5)
    bulletin_patterns = bulletin_store.get_pattern_strings(domain)
    return patterns + bulletin_patterns


def _get_storage_backend() -> LocalStorageBackend:
    """Create LocalStorageBackend from STORAGE_ROOT env var (default /tmp/agent-harness)."""
    root = os.environ.get("STORAGE_ROOT", "/tmp/agent-harness")
    return LocalStorageBackend(root=root)


async def _get_domain_memory_cached(backend: LocalStorageBackend, domain: str) -> str:
    """Return cached domain memory for this worker process."""
    if domain in _DOMAIN_MEMORY_CACHE:
        return _DOMAIN_MEMORY_CACHE[domain]
    memory = await load_domain_memory(backend, domain)
    _DOMAIN_MEMORY_CACHE[domain] = memory
    return memory


@activity.defn
async def santos_plan(input: PlannerInput) -> PlannerOutput:
    """Phase 1: Santos writes execution plan."""
    activity.logger.info("santos_plan: starting for %s", input.operativo_id)
    client = get_anthropic_client()
    backend = _get_storage_backend()
    domain_memory = await _get_domain_memory_cached(backend, input.domain)
    activity.logger.info("santos_plan: domain memory loaded (%d chars)", len(domain_memory))

    config = AgentConfig(
        name="santos",
        model=AGENT_MODELS["santos"],
        system_identity=SANTOS_SYSTEM_IDENTITY,
        domain=input.domain,
    )
    base_agent = BaseAgent(config)
    planner = SantosPlanner(base_agent=base_agent)

    semantic_patterns = await _retrieve_semantic_patterns(
        input.domain, f"plan operativo {input.operativo_id}: {input.pdf_description}"
    )
    activity.logger.info("santos_plan: calling planner.plan()")

    plan = await planner.plan(
        client=client,
        operativo_id=input.operativo_id,
        input_description=input.pdf_description,
        domain_memory=domain_memory,
        semantic_patterns=semantic_patterns,
    )
    activity.logger.info("santos_plan: plan done, %d steps", len(plan.tasks))

    get_cache_monitor().record(input.domain, "santos", client.total_usage)

    plan_json = json.dumps({"steps": [asdict(t) for t in plan.tasks]})

    return PlannerOutput(
        operativo_id=input.operativo_id,
        plan_json=plan_json,
        phase_result=f"Santos planned {len(plan.tasks)} steps for operativo {input.operativo_id}.",
    )


@activity.defn
async def medina_investigate(input: InvestigatorInput) -> InvestigatorOutput:
    """Phase 2: Medina investigates input document."""
    client = get_anthropic_client()
    backend = _get_storage_backend()
    domain_memory = await _get_domain_memory_cached(backend, input.domain)

    investigator = MedinaInvestigator(domain=input.domain)
    tool_handler = build_tool_handler(
        client,
        input.domain,
        operativo_id=input.operativo_id,
    )

    semantic_patterns = await _retrieve_semantic_patterns(
        input.domain, f"investigate document {input.pdf_filename}"
    )

    snapshot = await investigator.investigate(
        client=client,
        tool_handler=tool_handler,
        operativo_id=input.operativo_id,
        pdf_path=input.pdf_path,
        domain_memory=domain_memory,
        semantic_patterns=semantic_patterns,
    )

    get_cache_monitor().record(input.domain, "medina", client.total_usage)

    snapshot_json = json.dumps(asdict(snapshot))
    halted = snapshot.injection_scan_risk == "high"

    return InvestigatorOutput(
        operativo_id=input.operativo_id,
        input_snapshot_json=snapshot_json,
        injection_risk=snapshot.injection_scan_risk,
        phase_result=f"Medina investigated {input.pdf_filename}. Risk: {snapshot.injection_scan_risk}.",
        halted=halted,
    )


@activity.defn
async def lamponne_execute(input: AgentLoopInput) -> AgentLoopOutput:
    """Phase 3: Lamponne executes plan via DCE Backend APIs."""
    client = get_anthropic_client()
    backend = _get_storage_backend()
    domain_memory = await _get_domain_memory_cached(backend, input.domain)

    executor = LamponneExecutor(domain=input.domain, max_turns=input.max_turns)
    tool_handler = build_tool_handler(
        client,
        input.domain,
        operativo_id=input.operativo_id,
    )

    semantic_patterns = await _retrieve_semantic_patterns(
        input.domain, f"execute plan for operativo {input.operativo_id}"
    )

    result = await executor.execute(
        client=client,
        tool_handler=tool_handler,
        operativo_id=input.operativo_id,
        plan_json=input.task_message,
        domain_memory=domain_memory,
        semantic_patterns=semantic_patterns,
    )

    get_cache_monitor().record(input.domain, "lamponne", client.total_usage)

    return AgentLoopOutput(
        final_response=result,
        tool_calls_made=input.available_tools,
        turns_used=0,
    )


@activity.defn
async def santos_qa_review(input: QAReviewInput) -> QAReviewOutput:
    """Phase 4: Santos QA review."""
    client = get_anthropic_client()
    backend = _get_storage_backend()
    domain_memory = await _get_domain_memory_cached(backend, input.domain)

    reviewer = SantosQAReviewer(domain=input.domain)

    # Use checklist from input if provided, otherwise fall back to
    # the domain-specific default for DCE.
    checklist: list[str] | None = None
    if input.verify_checklist is not None:
        checklist = list(input.verify_checklist)
    elif input.domain == "dce":
        checklist = CPC_VERIFICATION_CHECKLIST

    semantic_patterns = await _retrieve_semantic_patterns(
        input.domain, f"qa review operativo {input.operativo_id}"
    )

    qa_report = await reviewer.review(
        client=client,
        operativo_id=input.operativo_id,
        input_snapshot_json=input.input_snapshot_json,
        raw_output_json=input.raw_output_json,
        domain_memory=domain_memory,
        verify_checklist=checklist,
        semantic_patterns=semantic_patterns,
        vision_extraction_json=input.vision_extraction_json,
        citation_completeness_report_json=input.citation_completeness_report_json,
        web_verification_evidence_json=input.web_verification_evidence_json,
    )

    get_cache_monitor().record(input.domain, "santos", client.total_usage)

    qa_report_json = json.dumps({
        "operativo_id": qa_report.operativo_id,
        "checks": [
            {
                "field": c.field,
                "expected": c.expected,
                "actual": c.actual,
                "severity": c.severity.name,
                "auto_correctable": c.auto_correctable,
                **({"citation_classification": c.citation_classification} if c.citation_classification else {}),
            }
            for c in qa_report.checks
        ],
        "correction_attempts": qa_report.correction_attempts,
    })

    final_status = "NEEDS_REVIEW" if qa_report.has_blocking else "COMPLETED"
    corrected_matrix_json = json.dumps(qa_report.corrected_citation_matrix, default=str)

    return QAReviewOutput(
        operativo_id=input.operativo_id,
        qa_report_json=qa_report_json,
        corrections_applied=qa_report.correction_attempts,
        final_status=final_status,
        phase_result=f"Santos QA: {len(qa_report.checks)} checks, {len(qa_report.corrected_citation_matrix)} citation corrections, status={final_status}.",
        corrected_citation_matrix_json=corrected_matrix_json,
    )


@activity.defn
async def cpc_web_verify(input: WebVerifyInput) -> WebVerifyOutput:
    """Run GCP-native web verification for ambiguous DCE citation cases."""
    queries = _build_web_verification_queries(
        input.citation_completeness_report_json, max_queries=input.max_queries
    )
    if not queries:
        payload = {"queries": [], "results": [], "used_google_search_grounding": False}
        return WebVerifyOutput(
            operativo_id=input.operativo_id,
            verification_json=json.dumps(payload),
            phase_result="Web verification skipped (no ambiguous citations).",
        )

    try:
        from google import genai
        from google.genai import types
    except Exception as exc:
        payload = {
            "queries": queries,
            "results": [],
            "used_google_search_grounding": False,
            "error": f"google-genai unavailable: {exc}",
        }
        return WebVerifyOutput(
            operativo_id=input.operativo_id,
            verification_json=json.dumps(payload, default=str),
            phase_result="Web verification unavailable (SDK import failed).",
        )

    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    region = os.environ.get("VERTEX_REGION", "us-central1")
    if not project:
        payload = {
            "queries": queries,
            "results": [],
            "used_google_search_grounding": False,
            "error": "GOOGLE_CLOUD_PROJECT not set",
        }
        return WebVerifyOutput(
            operativo_id=input.operativo_id,
            verification_json=json.dumps(payload),
            phase_result="Web verification unavailable (missing GCP project env).",
        )

    client = genai.Client(vertexai=True, project=project, location=region)
    model = "gemini-2.0-flash"
    results: list[dict[str, Any]] = []
    used_grounding = False

    for query in queries:
        prompt = (
            "Verify DCE citation claim using authoritative sources only (cpsc.gov, ecfr.gov). "
            "Return strict JSON object: {\"query\":...,\"finding\":...,\"confidence\":0-1,"
            "\"citations\":[{\"title\":...,\"url\":...}]}. Query: "
            + query
        )
        try:
            resp = await client.aio.models.generate_content(
                model=model,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.0,
                ),
            )
            used_grounding = True
        except Exception:
            resp = await client.aio.models.generate_content(
                model=model,
                contents=[prompt],
                config=types.GenerateContentConfig(temperature=0.0),
            )

        text = (resp.text or "").strip()
        parsed = _extract_json_object(text)
        if isinstance(parsed, dict):
            results.append(parsed)
        else:
            results.append({"query": query, "finding": text, "confidence": 0.4, "citations": []})

    payload = {
        "queries": queries,
        "results": results,
        "used_google_search_grounding": used_grounding,
    }
    return WebVerifyOutput(
        operativo_id=input.operativo_id,
        verification_json=json.dumps(payload, default=str),
        phase_result=f"Web verification completed for {len(results)} query(ies).",
    )


@activity.defn
async def ravenna_synthesize(input: SynthesizerInput) -> SynthesizerOutput:
    """Phase 5: Ravenna assembles final result."""
    client = get_anthropic_client()
    backend = _get_storage_backend()
    domain_memory = await _get_domain_memory_cached(backend, input.domain)

    synthesizer = RavennaSynthesizer(domain=input.domain)
    tool_handler = build_tool_handler(
        client,
        input.domain,
        operativo_id=input.operativo_id,
    )

    semantic_patterns = await _retrieve_semantic_patterns(
        input.domain, f"synthesize result for operativo {input.operativo_id}"
    )

    result = await synthesizer.synthesize(
        client=client,
        tool_handler=tool_handler,
        operativo_id=input.operativo_id,
        progress=input.progress_entries,
        raw_output_json=input.raw_output_json,
        qa_report_json=input.qa_report_json,
        caller_id=input.caller_id,
        domain_memory=domain_memory,
        semantic_patterns=semantic_patterns,
    )
    structured_result_json = _normalize_structured_result_json(
        operativo_id=input.operativo_id,
        domain=input.domain,
        raw_output_json=input.raw_output_json,
        qa_report_json=input.qa_report_json,
        synthesized_text=result,
        corrected_citation_matrix_json=input.corrected_citation_matrix_json,
        citation_completeness_report_json=input.citation_completeness_report_json,
        web_verification_evidence_json=input.web_verification_evidence_json,
    )

    get_cache_monitor().record(input.domain, "ravenna", client.total_usage)

    return SynthesizerOutput(
        operativo_id=input.operativo_id,
        structured_result_json=structured_result_json,
        report_url=f"/reports/{input.operativo_id}/structured_result.json",
        phase_result=f"Ravenna synthesized result for operativo {input.operativo_id}.",
        delivery_permitted=True,
    )


@activity.defn
async def post_job_learn(input: PostJobInput) -> PostJobOutput:
    """Phase 6: Post-job learning. Lightweight -- no LLM call needed.

    Creates a graph store, extracts learning patterns from the session
    progress log, and returns the count of patterns found.
    """
    # Production: use shared PostgresGraphStore connected to pgvector
    store = InMemoryGraphStore(embedder=FakeEmbeddingClient(dimensions=8))

    patterns_extracted = await extract_patterns(
        store=store,
        domain=input.domain,
        operativo_id=input.operativo_id,
        session_progress=input.session_progress,
    )

    return PostJobOutput(
        operativo_id=input.operativo_id,
        patterns_extracted=patterns_extracted,
        archived=True,
    )


@activity.defn
async def cortex_generate_bulletin(input: CortexScheduleInput) -> dict[str, Any]:
    """Generate a Cortex Bulletin -- cross-session memory summary.

    Retrieves recent patterns from the memory store, asks the LLM
    to summarize them, and returns the bulletin as a dict.
    """
    client = get_anthropic_client()
    recall = get_memory_recall()

    config = BulletinConfig(
        domain=input.domain,
        max_patterns=input.max_patterns,
        max_tokens=input.max_tokens,
    )

    bulletin = await generate_bulletin(client=client, recall=recall, config=config)

    return {
        "domain": bulletin.domain,
        "pattern_count": bulletin.pattern_count,
        "bulletin_summary": bulletin.summary,
        "generated_at": bulletin.generated_at,
    }
