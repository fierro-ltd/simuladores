"""CLI diagnostics for DCE workflow executions."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from agent_harness.config import load_config
from agent_harness.diagnostics.dce import collect_dce_diagnostics


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    cfg = load_config()
    parser = argparse.ArgumentParser(description="Inspect DCE workflow diagnostics.")
    parser.add_argument("workflow_id", help="Temporal workflow id (operativo id).")
    parser.add_argument(
        "--temporal-host",
        default=cfg.temporal.host,
        help="Temporal host:port (default from config/env).",
    )
    parser.add_argument(
        "--namespace",
        default=cfg.temporal.namespace,
        help="Temporal namespace (default from config/env).",
    )
    parser.add_argument(
        "--storage-root",
        default=os.environ.get("STORAGE_ROOT", "/tmp/agent-harness"),
        help="Storage root containing sessions/<workflow_id>/ artifacts.",
    )
    parser.add_argument(
        "--dce-backend-url",
        default="http://localhost:8000",
        help="Base URL for DCE Backend API.",
    )
    parser.add_argument("--json", action="store_true", help="Print full diagnostics JSON.")
    parser.add_argument(
        "--output",
        default="",
        help="Optional path to write diagnostics JSON artifact.",
    )
    return parser.parse_args()


def _print_human_summary(data: dict[str, Any]) -> None:
    """Print compact human-readable diagnostics summary."""
    workflow = data.get("workflow", {})
    phases = data.get("phases", {}).get("rollup", {})
    artifacts = data.get("artifacts", {})
    cpc_job = data.get("cpc_job")

    rows = [
        ("workflow_id", workflow.get("workflow_id")),
        ("run_id", workflow.get("run_id")),
        ("workflow_status", workflow.get("status")),
        ("history_length", workflow.get("history_length")),
        ("start_time", workflow.get("start_time")),
        ("close_time", workflow.get("close_time")),
        ("task_queue", workflow.get("task_queue")),
        ("cpc_job_id", artifacts.get("cpc_job_id")),
        ("cpc_job_status", cpc_job.get("status") if isinstance(cpc_job, dict) else None),
    ]
    width = max(len(str(k)) for k, _ in rows)
    print("\n" + "=" * 84)
    print("DCE Diagnostics")
    print("=" * 84)
    for key, value in rows:
        print(f"{key:<{width}} : {value}")

    print("\nPhase rollup:")
    if not phases:
        print("  (no activity rollup found)")
    else:
        for phase_name, phase_data in sorted(phases.items()):
            attempts = phase_data.get("attempts")
            total_s = phase_data.get("total_seconds")
            statuses = ",".join(phase_data.get("statuses", []))
            print(
                f"  - {phase_name}: attempts={attempts}, "
                f"total_seconds={total_s:.2f}, statuses={statuses}"
            )

    close_event = workflow.get("close_event") or {}
    if close_event:
        print("\nWorkflow close event:")
        print(json.dumps(close_event, indent=2, default=str))

    files = artifacts.get("files", [])
    print(f"\nArtifacts: {len(files)} files")
    for key in files[:15]:
        print(f"  - {key}")
    if len(files) > 15:
        print(f"  ... and {len(files) - 15} more")

    print("=" * 84)


async def main() -> int:
    """Collect and print DCE diagnostics."""
    args = parse_args()
    data = await collect_dce_diagnostics(
        workflow_id=args.workflow_id,
        temporal_host=args.temporal_host,
        namespace=args.namespace,
        storage_root=args.storage_root,
        dce_backend_url=args.dce_backend_url,
    )

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        print(f"Diagnostics written to {out_path}")

    if args.json:
        print(json.dumps(data, indent=2, default=str))
    else:
        _print_human_summary(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

