"""Cache control adapter for cross-provider prompt compatibility.

Anthropic's cache_control headers are provider-specific. This adapter
strips or passes them through based on the active provider gateway.
"""
from __future__ import annotations

import copy
from typing import Any

from agent_harness.core.provider_config import GatewayType, ProviderConfig


def apply_cache_control(
    messages: list[dict[str, Any]],
    provider: ProviderConfig,
) -> list[dict[str, Any]]:
    """Apply provider-specific cache control to messages.

    Anthropic: cache_control headers on content blocks — pass through
    OpenRouter (Anthropic models): same as Anthropic — pass through
    OpenRouter (non-Anthropic models): strip cache_control
    LiteLLM: pass through — LiteLLM handles per-backend via drop_params
    """
    if provider.gateway == GatewayType.DIRECT:
        return messages

    if provider.gateway == GatewayType.OPENROUTER:
        capable_model = provider.roles.get("capable", "")
        if "anthropic" in capable_model.lower():
            return messages
        return _strip_cache_control(messages)

    if provider.gateway == GatewayType.LITELLM:
        return messages

    return _strip_cache_control(messages)


def _strip_cache_control(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove cache_control from all content blocks."""
    cleaned = copy.deepcopy(messages)
    for msg in cleaned:
        if isinstance(msg.get("content"), list):
            for block in msg["content"]:
                if isinstance(block, dict):
                    block.pop("cache_control", None)
    return cleaned
