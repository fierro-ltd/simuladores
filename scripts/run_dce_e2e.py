"""Run a DCE end-to-end harness workflow and emit readable artifacts.

Default mode uses an existing long-lived DCE worker on task queue
``dce-operativo``. You can use ``--embedded-worker`` for self-contained runs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import shutil
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from temporalio.client import Client
from temporalio.worker import Worker

# Set env vars before importing harness modules
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "ai-acc-gen-dev")
os.environ.setdefault("VERTEX_REGION", "europe-west1")

from agent_harness.config import load_config
from agent_harness.domains.dce.operativo import CPCOperativoInput
from agent_harness.workers.dce import CPC_TASK_QUEUE, get_activity_list, get_workflow_list

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("e2e")


def parse_args() -> argparse.Namespace:
    """Parse CLI args for DCE e2e execution."""
    cfg = load_config()
    parser = argparse.ArgumentParser(description="Run DCE harness end-to-end workflow.")
    parser.add_argument(
        "pdf_path",
        nargs="?",
        default="/Users/metallo/Downloads/dce-sample-data/7810461-10000001109-DCE.pdf",
        help="Absolute path to DCE PDF file.",
    )
    parser.add_argument(
        "--temporal-host",
        default=cfg.temporal.host,
        help="Temporal host:port (default from TEMPORAL_HOST/config).",
    )
    parser.add_argument(
        "--namespace",
        default=cfg.temporal.namespace,
        help="Temporal namespace (default from TEMPORAL_NAMESPACE/config).",
    )
    parser.add_argument(
        "--workflow-id",
        default="",
        help="Optional workflow id. Default is dce-e2e-<random>.",
    )
    parser.add_argument(
        "--caller-id",
        default="e2e-test",
        help="Caller id stored in workflow input.",
    )
    parser.add_argument(
        "--task-queue",
        default=CPC_TASK_QUEUE,
        help="Task queue for workflow submission (default dce-operativo).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=5400,
        help="Overall timeout waiting for workflow result.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.environ.get("CPC_E2E_OUTPUT_DIR", os.path.join(os.getcwd(), ".dce-e2e-output")),
        help="Directory for JSON artifacts.",
    )
    parser.add_argument(
        "--embedded-worker",
        action="store_true",
        help="Run an in-process worker for this script (self-contained mode).",
    )
    parser.add_argument(
        "--e2e-fast-mode",
        action="store_true",
        help="Enable DCE workflow fast mode (reduced retries/time budgets, no post-job).",
    )
    parser.add_argument("--skip-navigation", action="store_true", help="Pass skip_navigation=True.")
    parser.add_argument("--skip-lab-check", action="store_true", help="Pass skip_lab_check=True.")
    parser.add_argument("--skip-photos", action="store_true", help="Pass skip_photos=True.")
    parser.add_argument(
        "--output-xlsx",
        default="",
        help="Copy citation matrix Excel to this path (e.g. /Users/metallo/Downloads/matrix.xlsx).",
    )
    return parser.parse_args()


def _to_dict(obj: Any) -> dict[str, Any]:
    """Convert dataclass-like output to dict."""
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, dict):
        return obj
    return {}


def _try_parse_json(value: Any) -> Any:
    """Parse JSON strings when possible, otherwise return input unchanged."""
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _to_serializable(obj: Any) -> dict[str, Any]:
    """Convert workflow output to readable structure with parsed nested JSON."""
    d = _to_dict(obj)
    sr = d.get("structured_result") or {}
    if isinstance(sr, dict):
        sr_resp = sr.get("response")
        sr["response"] = _try_parse_json(sr_resp)
    d["qa_summary"] = _try_parse_json(d.get("qa_summary"))
    return d


def _format_cpc_summary(result_dict: dict[str, Any], elapsed_s: float, workflow_id: str) -> str:
    """Build compact summary table for terminal output."""
    sr = result_dict.get("structured_result") or {}
    response = sr.get("response")
    parsed_response = response if isinstance(response, dict) else {}
    qa = parsed_response.get("qa_summary")
    if not isinstance(qa, dict):
        qa = result_dict.get("qa_summary") if isinstance(result_dict.get("qa_summary"), dict) else {}
    rows = [
        ("workflow_id", workflow_id),
        ("operativo_id", result_dict.get("operativo_id", "—")),
        ("status", str(result_dict.get("status", "—"))),
        ("elapsed_seconds", f"{elapsed_s:.1f}"),
        ("report_url", result_dict.get("report_url") or parsed_response.get("report_url") or "—"),
        ("qa_total_checks", qa.get("total_checks", "—")),
        ("qa_blocking", qa.get("blocking", "—")),
        ("qa_warnings", qa.get("warnings", "—")),
    ]
    col1_w = max(len(r[0]) for r in rows)
    lines = ["\n" + "─" * 72, "DCE E2E Summary", "─" * 72]
    for k, v in rows:
        lines.append(f"  {k:<{col1_w}}  {v}")
    lines.append("─" * 72)
    return "\n".join(lines)


def _build_key_fields(result_dict: dict[str, Any], workflow_id: str, elapsed_s: float) -> dict[str, Any]:
    """Extract quick-inspection fields from full workflow output."""
    structured = result_dict.get("structured_result") or {}
    response = structured.get("response")
    if not isinstance(response, dict):
        response = {}
    result_payload = response.get("result") if isinstance(response.get("result"), dict) else {}
    return {
        "workflow_id": workflow_id,
        "operativo_id": result_dict.get("operativo_id"),
        "status": result_dict.get("status"),
        "elapsed_seconds": elapsed_s,
        "report_url": result_dict.get("report_url"),
        "qa_summary": response.get("qa_summary", result_dict.get("qa_summary")),
        "result_keys": sorted(result_payload.keys()),
        "structured_status": response.get("status"),
        "result_preview": {
            "item_id": result_payload.get("item_id"),
            "job_id": result_payload.get("job_id"),
            "validation_status": (
                result_payload.get("validation", {}).get("overall_status")
                if isinstance(result_payload.get("validation"), dict)
                else None
            ),
        },
    }


async def _check_temporal_health(client: Client) -> bool:
    """Return True if Temporal service is reachable."""
    try:
        await asyncio.wait_for(client.service_client.check_health(), timeout=3.0)
        return True
    except Exception:
        return False


async def _run_embedded(
    client: Client,
    task_queue: str,
    workflow_id: str,
    workflow_input: CPCOperativoInput,
    timeout_seconds: int,
) -> Any:
    """Run workflow in self-contained mode with an embedded worker."""
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=get_workflow_list(),
        activities=get_activity_list(),
    )
    async with worker:
        logger.info("Embedded worker started on queue '%s'", task_queue)
        handle = await client.start_workflow(
            "CPCOperativoWorkflow",
            workflow_input,
            id=workflow_id,
            task_queue=task_queue,
        )
        logger.info("Workflow started: %s", workflow_id)
        return await asyncio.wait_for(handle.result(), timeout=timeout_seconds)


async def _run_with_existing_worker(
    client: Client,
    task_queue: str,
    workflow_id: str,
    workflow_input: CPCOperativoInput,
    timeout_seconds: int,
) -> Any:
    """Run workflow using an already-running DCE worker."""
    handle = await client.start_workflow(
        "CPCOperativoWorkflow",
        workflow_input,
        id=workflow_id,
        task_queue=task_queue,
    )
    logger.info("Workflow started: %s on queue %s", workflow_id, task_queue)
    return await asyncio.wait_for(handle.result(), timeout=timeout_seconds)


async def main() -> int:
    """Run e2e workflow and write artifacts."""
    args = parse_args()
    pdf_path = os.path.abspath(args.pdf_path)
    pdf_filename = os.path.basename(pdf_path)

    if not os.path.isfile(pdf_path):
        logger.error("PDF not found: %s", pdf_path)
        return 1

    run_suffix = uuid.uuid4().hex[:8]
    workflow_id = args.workflow_id or f"dce-e2e-{run_suffix}"
    task_queue = args.task_queue
    if args.embedded_worker and task_queue == CPC_TASK_QUEUE:
        # Isolate embedded runs from any long-lived workers on default queue.
        task_queue = f"dce-e2e-{run_suffix}"
        logger.info("Embedded mode using isolated task queue: %s", task_queue)
    workflow_input = CPCOperativoInput(
        pdf_path=pdf_path,
        pdf_filename=pdf_filename,
        caller_id=args.caller_id,
        skip_navigation=args.skip_navigation,
        skip_lab_check=args.skip_lab_check,
        skip_photos=args.skip_photos,
        e2e_fast_mode=args.e2e_fast_mode,
    )
    logger.info(
        "Connecting to Temporal at %s (namespace=%s)",
        args.temporal_host,
        args.namespace,
    )
    client = await Client.connect(args.temporal_host, namespace=args.namespace)

    if not await _check_temporal_health(client):
        logger.error("Temporal health check failed at %s (namespace=%s)", args.temporal_host, args.namespace)
        return 2

    started = time.monotonic()
    try:
        if args.embedded_worker:
            result = await _run_embedded(
                client=client,
                task_queue=task_queue,
                workflow_id=workflow_id,
                workflow_input=workflow_input,
                timeout_seconds=args.timeout_seconds,
            )
        else:
            result = await _run_with_existing_worker(
                client=client,
                task_queue=task_queue,
                workflow_id=workflow_id,
                workflow_input=workflow_input,
                timeout_seconds=args.timeout_seconds,
            )
    except asyncio.TimeoutError:
        logger.error("Workflow timed out after %ss (workflow_id=%s)", args.timeout_seconds, workflow_id)
        return 3
    except Exception as exc:
        logger.error("Workflow failed: %s", exc)
        try:
            handle = client.get_workflow_handle(workflow_id)
            desc = await handle.describe()
            logger.error("Workflow status: %s", desc.status)
        except Exception:
            pass
        return 4

    elapsed_s = time.monotonic() - started
    out = _to_serializable(result)
    key_fields = _build_key_fields(out, workflow_id=workflow_id, elapsed_s=elapsed_s)

    print(_format_cpc_summary(out, elapsed_s=elapsed_s, workflow_id=workflow_id))
    print("\n" + "=" * 80)
    print(json.dumps(key_fields, indent=2, default=str))
    print("=" * 80)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / workflow_id
    with (base.with_name(f"{base.name}_full.json")).open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    with (base.with_name(f"{base.name}_key_fields.json")).open("w", encoding="utf-8") as f:
        json.dump(key_fields, f, indent=2, default=str)
    logger.info("Artifacts written to %s_*", base)

    # -- Export citation matrix Excel if corrected_citation_matrix is present --
    from agent_harness.export.citation_matrix_excel import export_citation_matrix

    sr = out.get("structured_result") or {}
    response = sr.get("response")
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except json.JSONDecodeError:
            response = {}
    if isinstance(response, dict) and response.get("corrected_citation_matrix"):
        xlsx_path: Path | None = base.with_name(f"{base.name}_citation_matrix.xlsx")
        export_citation_matrix(
            structured_result=response,
            pdf_filename=pdf_filename,
            output_path=xlsx_path,
        )
        logger.info("Citation matrix Excel written to %s", xlsx_path)

        if args.output_xlsx and xlsx_path.exists():
            dest = Path(args.output_xlsx)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(xlsx_path, dest)
            logger.info("Citation matrix copied to %s", dest)
    else:
        logger.warning("No corrected_citation_matrix in structured result — Excel export skipped.")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
