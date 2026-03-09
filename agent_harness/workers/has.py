"""HAS Temporal worker — registers HAS workflow + activities.

Entry point: python -m agent_harness.workers.has
"""

from __future__ import annotations

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from agent_harness.config import load_config
from agent_harness.workers._shutdown import run_worker_with_graceful_shutdown
from agent_harness.workflows.has_workflow import CEEOperativoWorkflow

logger = logging.getLogger(__name__)

CEE_TASK_QUEUE = "has-operativo"


def get_workflow_list() -> list[type]:
    """Return workflow classes for the HAS worker."""
    return [CEEOperativoWorkflow]


def get_activity_list() -> list:
    """Return activity functions for the HAS worker.

    Uses lazy import to avoid importing heavy dependencies at module level.
    """
    from agent_harness.activities.implementations import (
        lamponne_execute,
        medina_investigate,
        post_job_learn,
        ravenna_synthesize,
        santos_plan,
        santos_qa_review,
    )
    from agent_harness.activities.callback import deliver_callback

    return [
        santos_plan,
        medina_investigate,
        lamponne_execute,
        santos_qa_review,
        ravenna_synthesize,
        post_job_learn,
        deliver_callback,
    ]


async def run_worker() -> None:
    """Start the HAS worker.

    Connects to Temporal, creates a Worker bound to the HAS task queue,
    registers the HAS workflow and all activity implementations, and runs
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
        task_queue=CEE_TASK_QUEUE,
        workflows=get_workflow_list(),
        activities=get_activity_list(),
    )

    logger.info("HAS worker started on task queue '%s'", CEE_TASK_QUEUE)
    await run_worker_with_graceful_shutdown(worker)


def main() -> None:
    """Entry point for python -m agent_harness.workers.has."""
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
