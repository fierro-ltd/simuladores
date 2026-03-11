"""FastAPI application for operativo intake and status.

Factory function ``create_app()`` returns a configured FastAPI instance.
The Temporal client is lazy-initialized on first use.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from agent_harness.config import load_config
from agent_harness.core.errors import ErrorCode, HarnessError
from agent_harness.gateway.auth import ApiKeyAuth
from agent_harness.gateway.dispatch import (
    DispatchError,
    dispatch_dce_operativo,
    dispatch_has_operativo,
    dispatch_idp_operativo,
)
from agent_harness.gateway.rate_limiter import InMemoryRateLimiter
from agent_harness.observability.audit import AuditEntry, AuditEvent, AuditLogger
from agent_harness.observability.cache_monitor import CacheMonitor
from agent_harness.workers.dce import CPC_TASK_QUEUE
from agent_harness.workers.has import CEE_TASK_QUEUE
from agent_harness.workers.idp import IDP_TASK_QUEUE

logger = logging.getLogger(__name__)

__version__ = "1.8.0"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CPCRequest(BaseModel):
    """Request body for creating a DCE operativo."""

    pdf_path: str
    pdf_filename: str
    caller_id: str
    callback_url: str | None = None
    skip_navigation: bool = False
    skip_lab_check: bool = False
    skip_photos: bool = False
    e2e_fast_mode: bool = False


class CPCResponse(BaseModel):
    """Response after submitting a DCE operativo."""

    operativo_id: str
    status: str
    task_queue: str


class CEERequest(BaseModel):
    """Request body for creating a HAS operativo."""

    document_path: str
    document_filename: str
    caller_id: str
    document_type: str
    guideline_version: str = "latest"
    audit_scope: str = "full"
    callback_url: str | None = None


class CEEResponse(BaseModel):
    """Response after submitting a HAS operativo."""

    operativo_id: str
    status: str
    task_queue: str


class IdpRequest(BaseModel):
    """Request body for creating an IDP operativo."""

    document_path: str
    plugin_id: str
    caller_id: str
    callback_url: str | None = None


class IdpResponse(BaseModel):
    """Response after submitting an IDP operativo."""

    operativo_id: str
    status: str
    task_queue: str


class StatusResponse(BaseModel):
    """Response for operativo status queries."""

    operativo_id: str
    status: str
    result: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    temporal: str = "unknown"


# ---------------------------------------------------------------------------
# Request ID middleware
# ---------------------------------------------------------------------------

class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assign a unique X-Request-ID to every request/response."""

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ---------------------------------------------------------------------------
# Temporal client singleton (lazy)
# ---------------------------------------------------------------------------

_temporal_client = None
_temporal_client_lock = asyncio.Lock()


async def _get_temporal_client():
    """Lazy-initialize and return Temporal client."""
    global _temporal_client  # noqa: PLW0603
    if _temporal_client is None:
        async with _temporal_client_lock:
            if _temporal_client is None:
                from temporalio.client import Client

                config = load_config()
                _temporal_client = await Client.connect(
                    config.temporal.host,
                    namespace=config.temporal.namespace,
                )
    return _temporal_client


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Create and return configured FastAPI application."""
    config = load_config()

    # Security components
    auth = ApiKeyAuth.from_env_string(config.gateway.api_keys)
    rate_limiter = InMemoryRateLimiter(
        max_requests=config.gateway.rate_limit_max,
        window_seconds=config.gateway.rate_limit_window,
    )
    audit = AuditLogger()
    cache_monitor = CacheMonitor()

    app = FastAPI(
        title="Agent Harness",
        version=__version__,
        description="Operativo intake and status API.",
    )

    # Observability
    from agent_harness.observability.logfire_config import configure_observability

    configure_observability(
        service_name="simuladores",
        environment="development",
        send_to_logfire=False,
        fastapi_app=app,
    )

    # Store on app state for access in tests
    app.state.auth = auth
    app.state.rate_limiter = rate_limiter
    app.state.audit = audit
    app.state.cache_monitor = cache_monitor

    # Middleware
    app.add_middleware(RequestIdMiddleware)

    # Global exception handler for HarnessError
    @app.exception_handler(HarnessError)
    async def harness_error_handler(request: Request, exc: HarnessError) -> JSONResponse:
        status_map = {
            ErrorCode.VALIDATION_ERROR: 400,
            ErrorCode.AUTH_REQUIRED: 401,
            ErrorCode.AUTH_INVALID: 401,
            ErrorCode.RATE_LIMITED: 429,
            ErrorCode.TEMPORAL_UNAVAILABLE: 503,
            ErrorCode.NOT_FOUND: 404,
            ErrorCode.INTERNAL_ERROR: 500,
        }
        status_code = status_map.get(exc.error_code, 500)
        # Attach request_id if available
        request_id = getattr(request.state, "request_id", None)
        if exc.request_id is None and request_id:
            exc = HarnessError(exc.error_code, exc.message, request_id=request_id)
        resp = exc.to_response()
        headers: dict[str, str] = {}
        if exc.error_code == ErrorCode.RATE_LIMITED:
            headers["Retry-After"] = "60"
        return JSONResponse(
            status_code=status_code,
            content=resp.to_dict(),
            headers=headers,
        )

    def _check_auth_and_rate(request: Request) -> str:
        """Run auth + rate limit checks, return caller_id. Raises HarnessError."""
        request_id = getattr(request.state, "request_id", "")

        # Auth
        api_key = request.headers.get("X-API-Key")
        auth_result = auth.authenticate(api_key)
        if not auth_result.authenticated:
            audit.log(AuditEntry(
                event=AuditEvent.AUTH_FAILURE,
                path=request.url.path,
                method=request.method,
                request_id=request_id,
            ))
            raise HarnessError(
                ErrorCode.AUTH_REQUIRED if api_key is None else ErrorCode.AUTH_INVALID,
                "Authentication required" if api_key is None else "Invalid API key",
                request_id=request_id,
            )

        caller_id = auth_result.caller_id or "anonymous"

        # Rate limit
        rl_result = rate_limiter.check(caller_id)
        if not rl_result.allowed:
            audit.log(AuditEntry(
                event=AuditEvent.RATE_LIMITED,
                caller_id=caller_id,
                path=request.url.path,
                method=request.method,
                request_id=request_id,
            ))
            raise HarnessError(
                ErrorCode.RATE_LIMITED,
                "Rate limit exceeded",
                request_id=request_id,
            )

        return caller_id

    @app.get("/observability/cache-stats")
    async def cache_stats() -> dict:
        """Return cache hit rate statistics per domain/agent."""
        return cache_monitor.summary()

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Health check endpoint with optional Temporal connectivity."""
        temporal_status = "unknown"
        try:
            client = await asyncio.wait_for(_get_temporal_client(), timeout=1.0)
            await asyncio.wait_for(
                client.service_client.check_health(),
                timeout=1.0,
            )
            temporal_status = "connected"
        except Exception:
            temporal_status = "unavailable"
        return HealthResponse(status="ok", version=__version__, temporal=temporal_status)

    @app.get("/health/ready", status_code=200)
    async def readiness() -> dict:
        """Readiness probe — returns 503 if Temporal is unavailable."""
        try:
            client = await asyncio.wait_for(_get_temporal_client(), timeout=1.0)
            await asyncio.wait_for(
                client.service_client.check_health(),
                timeout=1.0,
            )
        except Exception:
            from fastapi.responses import JSONResponse
            raise HTTPException(status_code=503, detail="Temporal unavailable")
        return {"status": "ready"}

    @app.post("/operativo/dce", response_model=CPCResponse, status_code=201)
    async def create_dce_operativo(request: Request, body: CPCRequest) -> CPCResponse:
        """Submit a new DCE operativo to Temporal."""
        caller_id = _check_auth_and_rate(request)
        request_id = getattr(request.state, "request_id", "")

        try:
            result = dispatch_dce_operativo(
                pdf_path=body.pdf_path,
                pdf_filename=body.pdf_filename,
                caller_id=body.caller_id,
                callback_url=body.callback_url,
                skip_navigation=body.skip_navigation,
                skip_lab_check=body.skip_lab_check,
                skip_photos=body.skip_photos,
                e2e_fast_mode=body.e2e_fast_mode,
            )
        except DispatchError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            client = await _get_temporal_client()
            from agent_harness.workflows.operativo_workflow import CPCOperativoWorkflow

            await client.start_workflow(
                CPCOperativoWorkflow.run,
                result.workflow_input,
                id=result.operativo_id,
                task_queue=CPC_TASK_QUEUE,
            )
        except Exception as exc:
            logger.error("Temporal submission failed: %s", exc)
            raise HTTPException(
                status_code=503,
                detail=f"Temporal unavailable: {exc}",
            ) from exc

        audit.log(AuditEntry(
            event=AuditEvent.DISPATCH,
            caller_id=caller_id,
            domain="dce",
            operativo_id=result.operativo_id,
            path="/operativo/dce",
            method="POST",
            status_code=201,
            request_id=request_id,
        ))

        return CPCResponse(
            operativo_id=result.operativo_id,
            status=result.status.value,
            task_queue=CPC_TASK_QUEUE,
        )

    @app.post("/operativo/has", response_model=CEEResponse, status_code=201)
    async def create_has_operativo(request: Request, body: CEERequest) -> CEEResponse:
        """Submit a new HAS operativo to Temporal."""
        caller_id = _check_auth_and_rate(request)
        request_id = getattr(request.state, "request_id", "")

        try:
            result = dispatch_has_operativo(
                document_path=body.document_path,
                document_filename=body.document_filename,
                caller_id=body.caller_id,
                document_type=body.document_type,
                guideline_version=body.guideline_version,
                audit_scope=body.audit_scope,
                callback_url=body.callback_url,
            )
        except DispatchError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            client = await _get_temporal_client()
            from agent_harness.workflows.has_workflow import CEEOperativoWorkflow

            await client.start_workflow(
                CEEOperativoWorkflow.run,
                result.workflow_input,
                id=result.operativo_id,
                task_queue=CEE_TASK_QUEUE,
            )
        except Exception as exc:
            logger.error("Temporal submission failed: %s", exc)
            raise HTTPException(
                status_code=503,
                detail=f"Temporal unavailable: {exc}",
            ) from exc

        audit.log(AuditEntry(
            event=AuditEvent.DISPATCH,
            caller_id=caller_id,
            domain="has",
            operativo_id=result.operativo_id,
            path="/operativo/has",
            method="POST",
            status_code=201,
            request_id=request_id,
        ))

        return CEEResponse(
            operativo_id=result.operativo_id,
            status=result.status.value,
            task_queue=CEE_TASK_QUEUE,
        )

    @app.post("/operativo/idp", response_model=IdpResponse, status_code=201)
    async def create_idp_operativo(request: Request, body: IdpRequest) -> IdpResponse:
        """Submit a new IDP operativo to Temporal."""
        caller_id = _check_auth_and_rate(request)
        request_id = getattr(request.state, "request_id", "")

        try:
            result = dispatch_idp_operativo(
                document_path=body.document_path,
                plugin_id=body.plugin_id,
                caller_id=body.caller_id,
                callback_url=body.callback_url,
            )
        except DispatchError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            client = await _get_temporal_client()
            from agent_harness.workflows.idp_workflow import IdpOperativoWorkflow

            await client.start_workflow(
                IdpOperativoWorkflow.run,
                result.workflow_input,
                id=result.operativo_id,
                task_queue=IDP_TASK_QUEUE,
            )
        except Exception as exc:
            logger.error("Temporal submission failed: %s", exc)
            raise HTTPException(
                status_code=503,
                detail=f"Temporal unavailable: {exc}",
            ) from exc

        audit.log(AuditEntry(
            event=AuditEvent.DISPATCH,
            caller_id=caller_id,
            domain="idp",
            operativo_id=result.operativo_id,
            path="/operativo/idp",
            method="POST",
            status_code=201,
            request_id=request_id,
        ))

        return IdpResponse(
            operativo_id=result.operativo_id,
            status=result.status.value,
            task_queue=IDP_TASK_QUEUE,
        )

    @app.get("/operativo/{operativo_id}/status", response_model=StatusResponse)
    async def get_operativo_status(request: Request, operativo_id: str) -> StatusResponse:
        """Query Temporal for operativo status."""
        _check_auth_and_rate(request)

        try:
            client = await _get_temporal_client()
            handle = client.get_workflow_handle(operativo_id)
            description = await handle.describe()
            status = description.status.name if description.status else "UNKNOWN"

            result = None
            if status in ("COMPLETED",):
                try:
                    result = await handle.result()
                except Exception as exc:
                    logger.warning(
                        "Failed to fetch result for operativo %s: %s",
                        operativo_id,
                        exc,
                    )

            return StatusResponse(
                operativo_id=operativo_id,
                status=status,
                result=result if isinstance(result, dict) else None,
            )
        except Exception as exc:
            logger.error("Failed to query operativo %s: %s", operativo_id, exc)
            raise HTTPException(
                status_code=503,
                detail=f"Temporal unavailable: {exc}",
            ) from exc

    return app


# Module-level app instance for uvicorn convenience
app = create_app()
