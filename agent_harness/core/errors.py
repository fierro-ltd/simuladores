"""Standardized error codes and error response types.

Provides a unified error model for the gateway and agents.
All API errors should use ``HarnessError`` so the gateway can
return a consistent JSON envelope.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Machine-readable error codes returned in API error envelopes."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_INVALID = "AUTH_INVALID"
    RATE_LIMITED = "RATE_LIMITED"
    TEMPORAL_UNAVAILABLE = "TEMPORAL_UNAVAILABLE"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True)
class ErrorResponse:
    """Serializable error envelope returned by the API."""

    error_code: ErrorCode
    message: str
    request_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        d: dict[str, Any] = {
            "error_code": str(self.error_code),
            "message": self.message,
        }
        if self.request_id is not None:
            d["request_id"] = self.request_id
        return d


class HarnessError(Exception):
    """Base exception carrying a structured error code.

    Raise this from gateway handlers or agents so the global
    exception handler can produce a consistent JSON response.
    """

    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.request_id = request_id

    def to_response(self) -> ErrorResponse:
        """Convert to an ``ErrorResponse``."""
        return ErrorResponse(
            error_code=self.error_code,
            message=self.message,
            request_id=self.request_id,
        )
