"""Callback delivery service — POST results to caller-provided URLs.

Never raises — always returns a CallbackResult. The workflow must not
fail because a callback endpoint is unreachable.
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 10
_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 1.0


@dataclass(frozen=True)
class CallbackResult:
    """Result of a callback delivery attempt."""

    url: str
    status_code: int
    success: bool
    error: str | None = None


class CallbackService:
    """Delivers operativo results to external callback URLs.

    Uses stdlib urllib so no extra dependencies are needed.
    Retries up to 3 times with exponential backoff (1s, 2s, 4s).
    """

    def __init__(
        self,
        timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = _MAX_RETRIES,
        backoff_base: float = _BACKOFF_BASE_SECONDS,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_base = backoff_base

    async def deliver(
        self, url: str, operativo_id: str, result: dict
    ) -> CallbackResult:
        """POST *result* as JSON to *url*. Never raises."""
        payload = {
            "operativo_id": operativo_id,
            "result": result,
        }
        body = json.dumps(payload).encode("utf-8")

        last_error: str | None = None
        last_status: int = 0

        for attempt in range(self.max_retries):
            if attempt > 0:
                delay = self.backoff_base * (2 ** (attempt - 1))
                logger.info(
                    "Callback retry %d/%d for %s (backoff=%.1fs)",
                    attempt + 1,
                    self.max_retries,
                    operativo_id,
                    delay,
                )
                await asyncio.sleep(delay)

            try:
                status_code = await self._post(url, body)
                if 200 <= status_code < 300:
                    logger.info(
                        "Callback delivered for %s -> %s (status=%d)",
                        operativo_id,
                        url,
                        status_code,
                    )
                    return CallbackResult(
                        url=url,
                        status_code=status_code,
                        success=True,
                    )
                last_status = status_code
                last_error = f"HTTP {status_code}"
            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}: {exc}"
                last_status = 0
                logger.warning(
                    "Callback attempt %d/%d failed for %s: %s",
                    attempt + 1,
                    self.max_retries,
                    operativo_id,
                    last_error,
                )

        logger.error(
            "Callback delivery failed after %d attempts for %s: %s",
            self.max_retries,
            operativo_id,
            last_error,
        )
        return CallbackResult(
            url=url,
            status_code=last_status,
            success=False,
            error=last_error,
        )

    async def _post(self, url: str, body: bytes) -> int:
        """Perform a synchronous POST in a thread to keep async context clean."""
        return await asyncio.to_thread(self._sync_post, url, body)

    def _sync_post(self, url: str, body: bytes) -> int:
        """Blocking POST using stdlib urllib."""
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                return resp.status
        except urllib.error.HTTPError as exc:
            return exc.code
