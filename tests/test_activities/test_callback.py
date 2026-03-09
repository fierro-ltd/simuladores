"""Tests for the deliver_callback Temporal activity."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from agent_harness.activities.callback import (
    CallbackInput,
    CallbackOutput,
    deliver_callback,
)
from agent_harness.gateway.callback import CallbackResult


class TestCallbackInput:
    def test_frozen(self):
        inp = CallbackInput(
            operativo_id="op-1",
            callback_url="http://example.com/cb",
            result_json='{"status": "COMPLETED"}',
        )
        assert inp.operativo_id == "op-1"
        with pytest.raises(AttributeError):
            inp.operativo_id = "op-2"  # type: ignore[misc]


class TestCallbackOutput:
    def test_success(self):
        out = CallbackOutput(success=True)
        assert out.success is True
        assert out.error is None

    def test_failure(self):
        out = CallbackOutput(success=False, error="timeout")
        assert out.success is False
        assert out.error == "timeout"


class TestDeliverCallbackActivity:
    async def test_successful_delivery(self):
        mock_result = CallbackResult(
            url="http://example.com/cb", status_code=200, success=True
        )
        with patch(
            "agent_harness.gateway.callback.CallbackService"
        ) as MockService:
            instance = MockService.return_value
            instance.deliver = AsyncMock(return_value=mock_result)

            inp = CallbackInput(
                operativo_id="op-1",
                callback_url="http://example.com/cb",
                result_json=json.dumps({"status": "COMPLETED"}),
            )
            output = await deliver_callback(inp)

        assert output.success is True
        assert output.error is None

    async def test_failed_delivery(self):
        mock_result = CallbackResult(
            url="http://example.com/cb",
            status_code=500,
            success=False,
            error="HTTP 500",
        )
        with patch(
            "agent_harness.gateway.callback.CallbackService"
        ) as MockService:
            instance = MockService.return_value
            instance.deliver = AsyncMock(return_value=mock_result)

            inp = CallbackInput(
                operativo_id="op-2",
                callback_url="http://example.com/cb",
                result_json=json.dumps({"status": "FAILED"}),
            )
            output = await deliver_callback(inp)

        assert output.success is False
        assert output.error == "HTTP 500"

    async def test_invalid_json_returns_error(self):
        inp = CallbackInput(
            operativo_id="op-3",
            callback_url="http://example.com/cb",
            result_json="not valid json {{{",
        )
        output = await deliver_callback(inp)

        assert output.success is False
        assert "Invalid result_json" in (output.error or "")

    async def test_activity_has_defn_decorator(self):
        """Verify the activity is properly decorated for Temporal."""
        assert hasattr(deliver_callback, "__temporal_activity_definition")
