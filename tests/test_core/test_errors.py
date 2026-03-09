"""Tests for core error codes and error response types."""

from __future__ import annotations

import pytest

from agent_harness.core.errors import ErrorCode, ErrorResponse, HarnessError


class TestErrorCode:
    """ErrorCode enum tests."""

    def test_all_codes_exist(self):
        expected = {
            "VALIDATION_ERROR",
            "AUTH_REQUIRED",
            "AUTH_INVALID",
            "RATE_LIMITED",
            "TEMPORAL_UNAVAILABLE",
            "NOT_FOUND",
            "INTERNAL_ERROR",
        }
        assert {c.value for c in ErrorCode} == expected

    def test_str_enum_behaviour(self):
        assert str(ErrorCode.AUTH_REQUIRED) == "AUTH_REQUIRED"
        assert ErrorCode.RATE_LIMITED == "RATE_LIMITED"


class TestErrorResponse:
    """ErrorResponse dataclass tests."""

    def test_to_dict_without_request_id(self):
        resp = ErrorResponse(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="bad input",
        )
        d = resp.to_dict()
        assert d == {"error_code": "VALIDATION_ERROR", "message": "bad input"}
        assert "request_id" not in d

    def test_to_dict_with_request_id(self):
        resp = ErrorResponse(
            error_code=ErrorCode.NOT_FOUND,
            message="not found",
            request_id="req-abc",
        )
        d = resp.to_dict()
        assert d["request_id"] == "req-abc"
        assert d["error_code"] == "NOT_FOUND"

    def test_frozen(self):
        resp = ErrorResponse(error_code=ErrorCode.INTERNAL_ERROR, message="oops")
        with pytest.raises(AttributeError):
            resp.message = "changed"  # type: ignore[misc]


class TestHarnessError:
    """HarnessError exception tests."""

    def test_is_exception(self):
        err = HarnessError(ErrorCode.AUTH_INVALID, "bad key")
        assert isinstance(err, Exception)
        assert str(err) == "bad key"

    def test_attributes(self):
        err = HarnessError(ErrorCode.RATE_LIMITED, "slow down", request_id="r-1")
        assert err.error_code == ErrorCode.RATE_LIMITED
        assert err.message == "slow down"
        assert err.request_id == "r-1"

    def test_to_response(self):
        err = HarnessError(ErrorCode.TEMPORAL_UNAVAILABLE, "down", request_id="r-2")
        resp = err.to_response()
        assert isinstance(resp, ErrorResponse)
        assert resp.error_code == ErrorCode.TEMPORAL_UNAVAILABLE
        assert resp.message == "down"
        assert resp.request_id == "r-2"

    def test_to_response_without_request_id(self):
        err = HarnessError(ErrorCode.INTERNAL_ERROR, "boom")
        resp = err.to_response()
        assert resp.request_id is None

    def test_raise_and_catch(self):
        with pytest.raises(HarnessError) as exc_info:
            raise HarnessError(ErrorCode.AUTH_REQUIRED, "login please")
        assert exc_info.value.error_code == ErrorCode.AUTH_REQUIRED
