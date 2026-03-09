"""Tests for health check endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from agent_harness.gateway.app import create_app


@pytest.fixture()
def client():
    """Create a TestClient for the app."""
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoint:
    def test_health_returns_ok(self, client: TestClient):
        """GET /health returns status ok."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_health_includes_version(self, client: TestClient):
        """GET /health includes version string."""
        response = client.get("/health")
        data = response.json()
        assert "version" in data
        assert len(data["version"]) > 0

    def test_health_temporal_field_present(self, client: TestClient):
        """GET /health includes temporal field."""
        response = client.get("/health")
        data = response.json()
        assert "temporal" in data
        # Without a running Temporal, should be "unavailable"
        assert data["temporal"] in ("connected", "unavailable", "unknown")


class TestReadinessEndpoint:
    def test_readiness_without_temporal(self):
        """GET /health/ready returns 503 when Temporal is unavailable."""
        # Ensure _get_temporal_client raises an error
        with patch(
            "agent_harness.gateway.app._get_temporal_client",
            side_effect=Exception("no temporal"),
        ):
            app = create_app()
            c = TestClient(app, raise_server_exceptions=False)
            response = c.get("/health/ready")
        assert response.status_code == 503

    def test_readiness_with_temporal(self):
        """GET /health/ready returns 200 when Temporal is connected."""
        mock_client = AsyncMock()
        mock_client.service_client.check_health = AsyncMock(return_value=None)

        with patch(
            "agent_harness.gateway.app._get_temporal_client",
            return_value=mock_client,
        ):
            app = create_app()
            c = TestClient(app)
            response = c.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    def test_health_temporal_connected_when_mocked(self):
        """GET /health shows temporal=connected when client is available."""
        mock_client = AsyncMock()
        mock_client.service_client.check_health = AsyncMock(return_value=None)

        with patch(
            "agent_harness.gateway.app._get_temporal_client",
            return_value=mock_client,
        ):
            app = create_app()
            c = TestClient(app)
            response = c.get("/health")
        data = response.json()
        assert data["temporal"] == "connected"
