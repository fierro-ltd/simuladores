"""Instructor-patched Anthropic client factory.

Creates an AsyncAnthropicVertex client wrapped with instructor for
structured output extraction via Pydantic models.
"""

from __future__ import annotations

import httpx
import instructor
from anthropic import AsyncAnthropicVertex

from agent_harness.config import load_config


def create_instructor_client(
    *,
    project_id: str | None = None,
    region: str | None = None,
) -> instructor.AsyncInstructor:
    """Create an instructor-patched AsyncAnthropicVertex client.

    Args:
        project_id: GCP project ID. Falls back to ``load_config().vertex.project_id``.
        region: Vertex AI region. Falls back to ``load_config().vertex.region``.

    Returns:
        An ``instructor.AsyncInstructor`` wrapping AsyncAnthropicVertex.
    """
    if project_id is None or region is None:
        cfg = load_config()
        project_id = project_id or cfg.vertex.project_id
        region = region or cfg.vertex.region

    base_client = AsyncAnthropicVertex(
        project_id=project_id,
        region=region,
        timeout=httpx.Timeout(120.0, connect=30.0),
    )

    return instructor.from_anthropic(base_client)
