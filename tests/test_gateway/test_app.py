"""Tests for the FastAPI gateway application."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from agent_harness.gateway.app import create_app
from agent_harness.gateway.dispatch import DispatchError


@pytest.fixture()
def client():
    """Create a TestClient for the app."""
    app = create_app()
    return TestClient(app)


def test_health_endpoint(client: TestClient):
    """GET /health returns status ok and version."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_create_dce_operativo_valid(client: TestClient):
    """POST /operativo/dce with valid input submits to Temporal and returns 201."""
    mock_temporal = AsyncMock()
    mock_temporal.start_workflow = AsyncMock(return_value=None)

    with patch(
        "agent_harness.gateway.app._get_temporal_client",
        return_value=mock_temporal,
    ):
        response = client.post(
            "/operativo/dce",
            json={
                "pdf_path": "/data/test.pdf",
                "pdf_filename": "test.pdf",
                "caller_id": "user-123",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["operativo_id"].startswith("dce-")
    assert data["status"] == "PENDING"
    assert data["task_queue"] == "dce-operativo"


def test_create_dce_operativo_missing_fields(client: TestClient):
    """POST /operativo/dce with missing required fields returns 422."""
    response = client.post(
        "/operativo/dce",
        json={"pdf_path": "/data/test.pdf"},
    )
    assert response.status_code == 422


def test_create_dce_operativo_invalid_pdf(client: TestClient):
    """POST /operativo/dce with non-PDF filename returns 400 from DispatchError."""
    response = client.post(
        "/operativo/dce",
        json={
            "pdf_path": "/data/test.txt",
            "pdf_filename": "test.txt",
            "caller_id": "user-123",
        },
    )
    assert response.status_code == 400
    assert "pdf" in response.json()["detail"].lower()


def test_create_has_operativo_valid(client: TestClient):
    """POST /operativo/has with valid input submits to Temporal and returns 201."""
    mock_temporal = AsyncMock()
    mock_temporal.start_workflow = AsyncMock(return_value=None)

    with patch(
        "agent_harness.gateway.app._get_temporal_client",
        return_value=mock_temporal,
    ):
        response = client.post(
            "/operativo/has",
            json={
                "document_path": "/data/attestation.pdf",
                "document_filename": "attestation.pdf",
                "caller_id": "user-123",
                "document_type": "attestation",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["operativo_id"].startswith("has-")
    assert data["status"] == "PENDING"
    assert data["task_queue"] == "has-operativo"


def test_create_has_operativo_missing_fields(client: TestClient):
    """POST /operativo/has with missing required fields returns 422."""
    response = client.post(
        "/operativo/has",
        json={"document_path": "/data/test.pdf"},
    )
    assert response.status_code == 422


def test_create_has_operativo_invalid_document_type(client: TestClient):
    """POST /operativo/has with invalid document_type returns 400."""
    response = client.post(
        "/operativo/has",
        json={
            "document_path": "/data/doc.pdf",
            "document_filename": "doc.pdf",
            "caller_id": "user-123",
            "document_type": "invalid_type",
        },
    )
    assert response.status_code == 400
    assert "document_type" in response.json()["detail"]


def test_create_idp_operativo_valid(client: TestClient):
    """POST /operativo/idp with valid input submits to Temporal and returns 201."""
    mock_temporal = AsyncMock()
    mock_temporal.start_workflow = AsyncMock(return_value=None)

    with patch(
        "agent_harness.gateway.app._get_temporal_client",
        return_value=mock_temporal,
    ):
        response = client.post(
            "/operativo/idp",
            json={
                "document_path": "/tmp/invoice.pdf",
                "plugin_id": "invoices",
                "caller_id": "user-123",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["operativo_id"].startswith("idp-")
    assert data["status"] == "PENDING"
    assert data["task_queue"] == "nav-operativo"


def test_create_idp_operativo_missing_fields(client: TestClient):
    """POST /operativo/idp with missing required fields returns 422."""
    response = client.post(
        "/operativo/idp",
        json={"caller_id": "user-123"},
    )
    assert response.status_code == 422


def test_create_idp_operativo_empty_document_path(client: TestClient):
    """POST /operativo/idp with empty document_path returns 400."""
    response = client.post(
        "/operativo/idp",
        json={
            "document_path": "",
            "plugin_id": "invoices",
            "caller_id": "user-123",
        },
    )
    assert response.status_code == 400
    assert "document_path" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Sprint 16 integration tests
# ---------------------------------------------------------------------------

class TestRequestId:
    """X-Request-ID middleware tests."""

    def test_response_has_request_id(self, client: TestClient):
        """Every response includes an X-Request-ID header."""
        response = client.get("/health")
        assert "X-Request-ID" in response.headers
        # Should be a valid UUID-like string
        assert len(response.headers["X-Request-ID"]) > 0

    def test_client_request_id_echoed(self, client: TestClient):
        """Client-provided X-Request-ID is echoed back."""
        response = client.get("/health", headers={"X-Request-ID": "my-id-123"})
        assert response.headers["X-Request-ID"] == "my-id-123"


class TestAuthIntegration:
    """Auth integration tests — verify disabled by default."""

    def test_auth_disabled_by_default(self, client: TestClient):
        """With no HARNESS_API_KEYS env var, auth is disabled and requests pass."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_auth_disabled_operativo_passes(self, client: TestClient):
        """Operativo endpoints pass without API key when auth disabled."""
        # This will fail at Temporal (dispatch error), not auth
        response = client.post(
            "/operativo/dce",
            json={
                "pdf_path": "/data/test.txt",
                "pdf_filename": "test.txt",
                "caller_id": "user-123",
            },
        )
        # 400 from dispatch, NOT 401 from auth
        assert response.status_code == 400

    def test_auth_enabled_rejects_missing_key(self):
        """With HARNESS_API_KEYS set, missing key returns 401."""
        with patch.dict(os.environ, {"HARNESS_API_KEYS": "sk-test:acme"}):
            app = create_app()
            c = TestClient(app, raise_server_exceptions=False)
            response = c.post(
                "/operativo/dce",
                json={
                    "pdf_path": "/data/test.pdf",
                    "pdf_filename": "test.pdf",
                    "caller_id": "user-123",
                },
            )
        assert response.status_code == 401
        assert response.json()["error_code"] == "AUTH_REQUIRED"

    def test_auth_enabled_rejects_invalid_key(self):
        """With HARNESS_API_KEYS set, wrong key returns 401."""
        with patch.dict(os.environ, {"HARNESS_API_KEYS": "sk-test:acme"}):
            app = create_app()
            c = TestClient(app, raise_server_exceptions=False)
            response = c.post(
                "/operativo/dce",
                json={
                    "pdf_path": "/data/test.pdf",
                    "pdf_filename": "test.pdf",
                    "caller_id": "user-123",
                },
                headers={"X-API-Key": "sk-wrong"},
            )
        assert response.status_code == 401
        assert response.json()["error_code"] == "AUTH_INVALID"

    def test_auth_enabled_accepts_valid_key(self):
        """With HARNESS_API_KEYS set and correct key, request proceeds."""
        with patch.dict(os.environ, {"HARNESS_API_KEYS": "sk-test:acme"}):
            app = create_app()
            c = TestClient(app, raise_server_exceptions=False)
            # Will fail at dispatch (bad pdf), not auth
            response = c.post(
                "/operativo/dce",
                json={
                    "pdf_path": "/data/test.txt",
                    "pdf_filename": "test.txt",
                    "caller_id": "user-123",
                },
                headers={"X-API-Key": "sk-test"},
            )
        assert response.status_code == 400  # dispatch error, not 401


class TestRateLimitIntegration:
    """Rate limit integration tests."""

    def test_rate_limit_disabled_by_default(self, client: TestClient):
        """With default config, rate limiting is disabled."""
        assert client.app.state.rate_limiter.enabled is False  # type: ignore[union-attr]

    def test_rate_limit_enabled_blocks(self):
        """When rate limit is enabled, excess requests return 429."""
        with patch.dict(os.environ, {"HARNESS_RATE_LIMIT_MAX": "1", "HARNESS_RATE_LIMIT_WINDOW": "60"}):
            app = create_app()
            c = TestClient(app, raise_server_exceptions=False)
            # First request passes (dispatch error, not rate limit)
            r1 = c.post(
                "/operativo/dce",
                json={
                    "pdf_path": "/data/test.txt",
                    "pdf_filename": "test.txt",
                    "caller_id": "user-123",
                },
            )
            assert r1.status_code == 400  # dispatch error

            # Second request rate-limited
            r2 = c.post(
                "/operativo/dce",
                json={
                    "pdf_path": "/data/test.pdf",
                    "pdf_filename": "test.pdf",
                    "caller_id": "user-123",
                },
            )
            assert r2.status_code == 429
            assert "Retry-After" in r2.headers
            assert r2.json()["error_code"] == "RATE_LIMITED"


# ---------------------------------------------------------------------------
# Sprint 17 — Cache stats endpoint tests
# ---------------------------------------------------------------------------

class TestCacheStatsEndpoint:
    """Tests for GET /observability/cache-stats."""

    def test_cache_stats_endpoint_returns_json(self, client: TestClient):
        """GET /observability/cache-stats returns valid JSON with expected keys."""
        response = client.get("/observability/cache-stats")
        assert response.status_code == 200
        data = response.json()
        assert "by_domain_agent" in data
        assert "overall_hit_rate" in data

    def test_cache_stats_empty_initially(self, client: TestClient):
        """Cache stats are empty when no LLM calls have been made."""
        response = client.get("/observability/cache-stats")
        data = response.json()
        assert data["by_domain_agent"] == []
        assert data["overall_hit_rate"] == 0.0
