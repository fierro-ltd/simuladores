"""DCE workflow diagnostics utilities."""

from __future__ import annotations

import datetime as dt
import os
from collections import defaultdict
from typing import Any

import httpx
from temporalio.client import Client

from agent_harness.config import load_config
from agent_harness.storage.local import LocalStorageBackend

_PHASE_ACTIVITY_MAP = {
    "phase_1_plan": {"santos_plan"},
    "phase_2a_investigate": {"medina_investigate"},
    "phase_2b_vision": {"gemini_vision_extract"},
    "phase_3_execute": {"lamponne_execute"},
    "phase_4_qa": {"santos_qa_review"},
    "phase_5_synthesize": {"ravenna_synthesize"},
    "phase_6_post_job": {"post_job_learn"},
    "callback": {"deliver_callback"},
}

_TERMINAL_ACTIVITY_ATTRS = {
    "activity_task_completed_event_attributes": "completed",
    "activity_task_failed_event_attributes": "failed",
    "activity_task_timed_out_event_attributes": "timed_out",
    "activity_task_canceled_event_attributes": "canceled",
}

_WORKFLOW_CLOSE_ATTRS = {
    "workflow_execution_completed_event_attributes": "completed",
    "workflow_execution_failed_event_attributes": "failed",
    "workflow_execution_timed_out_event_attributes": "timed_out",
    "workflow_execution_terminated_event_attributes": "terminated",
    "workflow_execution_canceled_event_attributes": "canceled",
}


def _ts_to_iso(ts: Any) -> str | None:
    """Convert protobuf timestamp-like object to ISO8601."""
    if ts is None:
        return None
    seconds = getattr(ts, "seconds", None)
    nanos = getattr(ts, "nanos", 0)
    if seconds is None:
        return None
    epoch = float(seconds) + (float(nanos) / 1_000_000_000)
    return dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc).isoformat()


def _ts_to_epoch(ts: Any) -> float | None:
    """Convert protobuf timestamp-like object to unix epoch seconds."""
    if ts is None:
        return None
    seconds = getattr(ts, "seconds", None)
    nanos = getattr(ts, "nanos", 0)
    if seconds is None:
        return None
    return float(seconds) + (float(nanos) / 1_000_000_000)


def _duration_seconds(start_ts: Any, end_ts: Any) -> float | None:
    """Compute duration from two protobuf timestamp-like objects."""
    start = _ts_to_epoch(start_ts)
    end = _ts_to_epoch(end_ts)
    if start is None or end is None:
        return None
    return max(0.0, end - start)


def _phase_name_for_activity(activity_name: str) -> str:
    """Map activity name to phase label."""
    for phase_name, activity_names in _PHASE_ACTIVITY_MAP.items():
        if activity_name in activity_names:
            return phase_name
    return "other"


async def _read_storage_artifacts(storage_root: str, workflow_id: str) -> dict[str, Any]:
    """Read key session artifacts for a workflow id."""
    backend = LocalStorageBackend(root=storage_root)
    prefix = f"sessions/{workflow_id}"
    files = await backend.list(prefix)

    artifacts: dict[str, Any] = {
        "storage_root": storage_root,
        "session_prefix": prefix,
        "files": sorted(files),
        "cpc_job_id": None,
        "progress_excerpt": None,
    }

    cpc_job_id_key = f"{prefix}/cpc_job_id.txt"
    if await backend.exists(cpc_job_id_key):
        artifacts["cpc_job_id"] = (await backend.read(cpc_job_id_key)).decode("utf-8").strip()

    progress_key = f"{prefix}/PROGRESS.md"
    if await backend.exists(progress_key):
        progress = (await backend.read(progress_key)).decode("utf-8", errors="replace")
        artifacts["progress_excerpt"] = progress[:2000]

    return artifacts


async def _read_cpc_job_status(dce_backend_url: str, job_id: str | None) -> dict[str, Any] | None:
    """Fetch DCE API job status if job_id is available."""
    if not job_id:
        return None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{dce_backend_url}/jobs/{job_id}")
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        return {"job_id": job_id, "error": str(exc)}


async def collect_dce_diagnostics(
    workflow_id: str,
    temporal_host: str | None = None,
    namespace: str | None = None,
    storage_root: str | None = None,
    dce_backend_url: str | None = None,
) -> dict[str, Any]:
    """Collect DCE diagnostics for a given workflow id."""
    cfg = load_config()
    temporal_host = temporal_host or cfg.temporal.host
    namespace = namespace or cfg.temporal.namespace
    storage_root = storage_root or os.environ.get("STORAGE_ROOT", "/tmp/agent-harness")
    dce_backend_url = dce_backend_url or "http://localhost:8000"

    client = await Client.connect(temporal_host, namespace=namespace)
    handle = client.get_workflow_handle(workflow_id)
    describe = await handle.describe()
    info = describe.raw_description.workflow_execution_info
    workflow_status = getattr(describe.status, "name", str(describe.status))

    scheduled_by_event_id: dict[int, dict[str, Any]] = {}
    activities: list[dict[str, Any]] = []
    close_event: dict[str, Any] | None = None

    async for event in handle.fetch_history_events():
        attr = event.WhichOneof("attributes")
        if attr == "activity_task_scheduled_event_attributes":
            details = getattr(event, attr)
            scheduled_by_event_id[event.event_id] = {
                "activity_name": details.activity_type.name,
                "activity_id": details.activity_id,
                "scheduled_event_id": event.event_id,
                "scheduled_at": _ts_to_iso(event.event_time),
                "scheduled_at_ts": event.event_time,
                "started_at": None,
                "closed_at": None,
                "close_status": None,
                "failure": None,
            }
            continue

        if attr == "activity_task_started_event_attributes":
            details = getattr(event, attr)
            entry = scheduled_by_event_id.get(details.scheduled_event_id)
            if entry is not None:
                entry["started_at"] = _ts_to_iso(event.event_time)
                entry["started_at_ts"] = event.event_time
            continue

        if attr in _TERMINAL_ACTIVITY_ATTRS:
            details = getattr(event, attr)
            entry = scheduled_by_event_id.get(details.scheduled_event_id)
            if entry is not None:
                entry["closed_at"] = _ts_to_iso(event.event_time)
                entry["closed_at_ts"] = event.event_time
                entry["close_status"] = _TERMINAL_ACTIVITY_ATTRS[attr]
                if attr == "activity_task_failed_event_attributes":
                    failure = getattr(details, "failure", None)
                    entry["failure"] = getattr(failure, "message", "") if failure else ""
                entry["duration_seconds"] = _duration_seconds(
                    entry.get("started_at_ts") or entry.get("scheduled_at_ts"),
                    entry.get("closed_at_ts"),
                )
                activities.append(
                    {
                        "phase": _phase_name_for_activity(entry["activity_name"]),
                        "activity_name": entry["activity_name"],
                        "activity_id": entry["activity_id"],
                        "scheduled_event_id": entry["scheduled_event_id"],
                        "scheduled_at": entry["scheduled_at"],
                        "started_at": entry["started_at"],
                        "closed_at": entry["closed_at"],
                        "close_status": entry["close_status"],
                        "duration_seconds": entry.get("duration_seconds"),
                        "failure": entry["failure"],
                    }
                )
            continue

        if attr in _WORKFLOW_CLOSE_ATTRS:
            close_event = {
                "status": _WORKFLOW_CLOSE_ATTRS[attr],
                "closed_at": _ts_to_iso(event.event_time),
            }
            details = getattr(event, attr)
            reason = getattr(details, "reason", "")
            if reason:
                close_event["reason"] = reason
            if attr == "workflow_execution_failed_event_attributes":
                failure = getattr(details, "failure", None)
                if failure and getattr(failure, "message", None):
                    close_event["failure_message"] = failure.message

    phase_rollup: dict[str, Any] = defaultdict(lambda: {"attempts": 0, "total_seconds": 0.0, "statuses": []})
    for activity_item in activities:
        phase = activity_item["phase"]
        phase_rollup[phase]["attempts"] += 1
        phase_rollup[phase]["statuses"].append(activity_item.get("close_status"))
        duration = activity_item.get("duration_seconds")
        if isinstance(duration, (int, float)):
            phase_rollup[phase]["total_seconds"] += float(duration)

    storage = await _read_storage_artifacts(storage_root=storage_root, workflow_id=workflow_id)
    cpc_job = await _read_cpc_job_status(dce_backend_url=dce_backend_url, job_id=storage.get("cpc_job_id"))

    return {
        "workflow": {
            "workflow_id": workflow_id,
            "run_id": info.execution.run_id,
            "status": workflow_status,
            "history_length": int(info.history_length),
            "start_time": _ts_to_iso(info.start_time),
            "close_time": _ts_to_iso(info.close_time),
            "task_queue": describe.task_queue,
            "close_event": close_event,
            "temporal_host": temporal_host,
            "namespace": namespace,
        },
        "phases": {
            "rollup": dict(phase_rollup),
            "activities": activities,
        },
        "artifacts": storage,
        "cpc_job": cpc_job,
    }

