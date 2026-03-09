"""Graceful shutdown utilities for Temporal workers.

Installs SIGTERM/SIGINT handlers that trigger a clean drain of the
worker. On Windows, signal handlers are skipped (not supported).
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from temporalio.worker import Worker

logger = logging.getLogger(__name__)


def create_shutdown_event() -> asyncio.Event:
    """Create an asyncio.Event and wire SIGTERM/SIGINT to set it.

    On Windows, signal handlers are not installed (unsupported by asyncio
    on that platform). Returns the event so callers can await it.
    """
    shutdown_event = asyncio.Event()

    if sys.platform == "win32":
        logger.debug("Skipping signal handlers on Windows")
        return shutdown_event

    loop = asyncio.get_running_loop()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received, draining...")
        shutdown_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    return shutdown_event


async def run_worker_with_graceful_shutdown(
    worker: Worker,
    max_drain_seconds: float | None = 60.0,
) -> None:
    """Run *worker* until completion or a shutdown signal.

    On SIGTERM/SIGINT the worker is shut down gracefully, allowing
    in-flight activities to complete before the process exits.
    """
    shutdown_event = create_shutdown_event()

    worker_task = asyncio.create_task(worker.run())
    shutdown_task = asyncio.create_task(shutdown_event.wait())

    done, pending = await asyncio.wait(
        {worker_task, shutdown_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    if shutdown_task in done:
        logger.info("Initiating graceful worker shutdown...")
        shutdown_result = worker.shutdown()
        if asyncio.iscoroutine(shutdown_result):
            await shutdown_result
        # Wait for the worker task to finish draining
        try:
            if max_drain_seconds is None:
                await worker_task
            else:
                await asyncio.wait_for(worker_task, timeout=max_drain_seconds)
        except asyncio.TimeoutError:
            logger.warning(
                "Worker drain exceeded %.1fs; cancelling worker task",
                max_drain_seconds,
            )
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
        except asyncio.CancelledError:
            pass
        logger.info("Worker shut down gracefully.")
    else:
        # Worker exited on its own (error or clean exit)
        shutdown_task.cancel()
        # Re-raise any worker exception
        worker_task.result()
