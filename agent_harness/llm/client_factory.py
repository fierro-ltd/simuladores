"""Provider-aware LLM client factory.

Builds instructor-patched clients for any supported gateway (Anthropic Vertex,
OpenRouter, LiteLLM) based on the active ProviderConfig.
"""
from __future__ import annotations

import instructor
from instructor import AsyncInstructor

from agent_harness.core.provider_config import ProviderConfig, GatewayType


def build_instructor_client(
    provider: ProviderConfig,
    role: str,
) -> tuple[AsyncInstructor, str, int]:
    """Build an instructor client for the given provider and role.

    Returns:
        (instructor_client, resolved_model_string, max_retries)
    """
    model_string = provider.resolve_model(role)

    match provider.gateway:
        case GatewayType.DIRECT:
            # Current path — Anthropic SDK via Vertex AI
            from anthropic import AsyncAnthropicVertex
            import os
            import httpx
            raw_client = AsyncAnthropicVertex(
                project_id=os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
                region=os.environ.get("VERTEX_REGION", "us-east5"),
                timeout=httpx.Timeout(120.0, connect=30.0),
            )
            client = instructor.from_anthropic(raw_client)

        case GatewayType.OPENROUTER:
            # OpenRouter via OpenAI-compatible API
            from openai import AsyncOpenAI
            import os
            raw_client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.environ.get("OPENROUTER_API_KEY", ""),
                default_headers={
                    "HTTP-Referer": os.environ.get(
                        "OPENROUTER_REFERER", "https://fierro.co.uk"
                    ),
                    "X-Title": "Simuladores",
                },
            )
            client = instructor.from_openai(raw_client, mode=instructor.Mode.JSON)

        case GatewayType.LITELLM:
            # Self-hosted LiteLLM proxy — OpenAI-compatible API
            from openai import AsyncOpenAI
            import os
            raw_client = AsyncOpenAI(
                base_url=provider.base_url,
                api_key=os.environ.get("LITELLM_API_KEY", "sk-simuladores"),
            )
            client = instructor.from_openai(raw_client, mode=instructor.Mode.JSON)

        case _:
            raise ValueError(f"Unknown gateway type: {provider.gateway}")

    # Retry budget scales with provider reliability
    max_retries = {
        GatewayType.DIRECT: 2,
        GatewayType.OPENROUTER: 3,
        GatewayType.LITELLM: 3,
    }.get(provider.gateway, 3)

    return client, model_string, max_retries
