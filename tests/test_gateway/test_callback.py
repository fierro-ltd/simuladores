"""Tests for the callback delivery service."""

from __future__ import annotations

import asyncio
from unittest.mock import patch, MagicMock

import pytest

from agent_harness.gateway.callback import CallbackResult, CallbackService


@pytest.fixture
def service() -> CallbackService:
    """Create a CallbackService with no backoff for fast tests."""
    return CallbackService(timeout_seconds=2, max_retries=3, backoff_base=0.0)


class TestCallbackResult:
    def test_frozen_dataclass(self):
        r = CallbackResult(url="http://x", status_code=200, success=True)
        assert r.url == "http://x"
        assert r.status_code == 200
        assert r.success is True
        assert r.error is None

    def test_with_error(self):
        r = CallbackResult(url="http://x", status_code=500, success=False, error="boom")
        assert r.error == "boom"


class TestSuccessfulDelivery:
    async def test_successful_delivery(self, service: CallbackService):
        """A 200 response should return success=True."""
        with patch.object(service, "_post", return_value=200) as mock_post:
            result = await service.deliver(
                url="http://example.com/callback",
                operativo_id="op-123",
                result={"status": "COMPLETED"},
            )
        assert result.success is True
        assert result.status_code == 200
        assert result.error is None
        assert result.url == "http://example.com/callback"
        mock_post.assert_called_once()


class TestDeliveryFailure:
    async def test_delivery_failure_returns_result(self, service: CallbackService):
        """HTTP 500 on all attempts should return success=False with error."""
        with patch.object(service, "_post", return_value=500):
            result = await service.deliver(
                url="http://example.com/callback",
                operativo_id="op-123",
                result={"status": "COMPLETED"},
            )
        assert result.success is False
        assert result.status_code == 500
        assert result.error == "HTTP 500"


class TestTimeout:
    async def test_timeout_returns_result(self, service: CallbackService):
        """Timeout exceptions should be caught and returned as failure."""
        with patch.object(
            service, "_post", side_effect=TimeoutError("connection timed out")
        ):
            result = await service.deliver(
                url="http://example.com/callback",
                operativo_id="op-123",
                result={"status": "COMPLETED"},
            )
        assert result.success is False
        assert "TimeoutError" in (result.error or "")


class TestRetries:
    async def test_retries_on_failure(self, service: CallbackService):
        """Should retry up to max_retries times before giving up."""
        with patch.object(service, "_post", return_value=503) as mock_post:
            result = await service.deliver(
                url="http://example.com/callback",
                operativo_id="op-123",
                result={},
            )
        assert result.success is False
        assert mock_post.call_count == 3  # max_retries

    async def test_retries_succeed_on_second_attempt(self, service: CallbackService):
        """Should succeed if a retry returns 200."""
        with patch.object(service, "_post", side_effect=[503, 200]) as mock_post:
            result = await service.deliver(
                url="http://example.com/callback",
                operativo_id="op-456",
                result={},
            )
        assert result.success is True
        assert mock_post.call_count == 2


class TestNeverRaises:
    async def test_never_raises_on_connection_error(self, service: CallbackService):
        """Even a completely broken URL should return a result, not raise."""
        with patch.object(
            service, "_post", side_effect=ConnectionError("DNS failure")
        ):
            result = await service.deliver(
                url="http://this-does-not-exist.invalid/callback",
                operativo_id="op-999",
                result={},
            )
        assert result.success is False
        assert result.error is not None

    async def test_never_raises_on_unexpected_exception(self, service: CallbackService):
        """Even unexpected exceptions should be swallowed."""
        with patch.object(
            service, "_post", side_effect=RuntimeError("unexpected")
        ):
            result = await service.deliver(
                url="http://example.com/cb",
                operativo_id="op-000",
                result={},
            )
        assert result.success is False
        assert "RuntimeError" in (result.error or "")
