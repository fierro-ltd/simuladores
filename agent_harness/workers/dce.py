"""DCE Temporal worker — registers DCE workflow + activities.

Entry point: python -m agent_harness.workers.dce
"""

from __future__ import annotations

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from agent_harness.config import load_config
from agent_harness.workers._shutdown import run_worker_with_graceful_shutdown
from agent_harness.workflows.cortex import CortexBulletinWorkflow
from agent_harness.workflows.operativo_workflow import CPCOperativoWorkflow

logger = logging.getLogger(__name__)

CPC_TASK_QUEUE = "dce-operativo"


def get_workflow_list() -> list[type]:
    """Return workflow classes for the DCE worker."""
    return [CPCOperativoWorkflow, CortexBulletinWorkflow]


def get_activity_list() -> list:
    """Return activity functions for the DCE worker.

    Uses lazy import to avoid importing heavy dependencies at module level.
    """
    from agent_harness.activities.implementations import (
        cpc_web_verify,
        cortex_generate_bulletin,
        lamponne_execute,
        medina_investigate,
        post_job_learn,
        ravenna_synthesize,
        santos_plan,
        santos_qa_review,
    )
    from agent_harness.activities.vision_extract import gemini_vision_extract
    from agent_harness.activities.callback import deliver_callback

    return [
        santos_plan,
        medina_investigate,
        gemini_vision_extract,
        lamponne_execute,
        cpc_web_verify,
        santos_qa_review,
        ravenna_synthesize,
        post_job_learn,
        deliver_callback,
        cortex_generate_bulletin,
    ]


async def run_worker() -> None:
    """Start the DCE worker.

    Connects to Temporal, creates a Worker bound to the DCE task queue,
    registers the DCE workflow and all activity implementations, and runs
    with graceful shutdown support (SIGTERM/SIGINT).
    """
    config = load_config()
    logger.info(
        "Connecting to Temporal at %s (namespace=%s)",
        config.temporal.host,
        config.temporal.namespace,
    )

    client = await Client.connect(
        config.temporal.host,
        namespace=config.temporal.namespace,
    )

    worker = Worker(
        client,
        task_queue=CPC_TASK_QUEUE,
        workflows=get_workflow_list(),
        activities=get_activity_list(),
    )

    logger.info("DCE worker started on task queue '%s'", CPC_TASK_QUEUE)
    await run_worker_with_graceful_shutdown(worker, max_drain_seconds=90.0)


def main() -> None:
    """Entry point for python -m agent_harness.workers.dce."""
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
