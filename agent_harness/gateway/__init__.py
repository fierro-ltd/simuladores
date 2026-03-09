"""API gateway for operativo intake."""

from agent_harness.gateway.auth import (
    ApiKeyAuth,
    AuthResult,
)
from agent_harness.gateway.dispatch import (
    DispatchResult,
    DispatchError,
    dispatch_dce_operativo,
    dispatch_has_operativo,
    dispatch_idp_operativo,
)
from agent_harness.gateway.email_intake import (
    AttachmentRef,
    EmailIntakePayload,
    EmailIntakeError,
    validate_email_payload,
    find_pdf_attachment,
)
from agent_harness.gateway.rate_limiter import (
    InMemoryRateLimiter,
    RateLimitResult,
)
from agent_harness.gateway.router import (
    RouteResult,
    RouteError,
    build_default_registry,
    route_operativo,
)
from agent_harness.gateway.app import create_app

__all__ = [
    "ApiKeyAuth",
    "AttachmentRef",
    "AuthResult",
    "DispatchError",
    "DispatchResult",
    "EmailIntakeError",
    "EmailIntakePayload",
    "InMemoryRateLimiter",
    "RateLimitResult",
    "RouteError",
    "RouteResult",
    "build_default_registry",
    "create_app",
    "dispatch_has_operativo",
    "dispatch_dce_operativo",
    "dispatch_idp_operativo",
    "find_pdf_attachment",
    "route_operativo",
    "validate_email_payload",
]
