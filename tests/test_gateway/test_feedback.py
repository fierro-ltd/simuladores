"""Tests for feedback gateway endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agent_harness.gateway.app import create_app


@pytest.fixture()
def client():
    """Create a TestClient for the app."""
    app = create_app()
    return TestClient(app)


def test_feedback_endpoint_accepts_request(client: TestClient):
    """POST /operativos/{id}/feedback with valid body returns 202."""
    response = client.post(
        "/operativos/dce-001/feedback",
        json={
            "action": "corrected",
            "corrected_verdict": "PASS",
            "corrected_citations": ["section 4.2"],
            "reviewer_notes": "Missing citation",
        },
    )
    assert response.status_code == 202


def test_feedback_endpoint_returns_operativo_id(client: TestClient):
    """Response includes the operativo_id from the URL path."""
    response = client.post(
        "/operativos/dce-042/feedback",
        json={"action": "accepted"},
    )
    assert response.status_code == 202
    data = response.json()
    assert data["operativo_id"] == "dce-042"
    assert data["status"] == "feedback_queued"
