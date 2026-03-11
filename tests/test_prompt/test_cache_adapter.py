"""Tests for cache control adapter across providers."""
from __future__ import annotations

import copy

from agent_harness.core.provider_config import GatewayType, ProviderConfig
from agent_harness.prompt.cache_adapter import apply_cache_control, _strip_cache_control


MESSAGES_WITH_CACHE = [
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "Hello",
                "cache_control": {"type": "ephemeral"},
            }
        ],
    },
    {
        "role": "assistant",
        "content": "Hi there",
    },
]

MESSAGES_WITHOUT_CACHE = [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi"},
]


def _make_provider(
    gateway: GatewayType,
    roles: dict[str, str] | None = None,
) -> ProviderConfig:
    return ProviderConfig(
        name="test",
        gateway=gateway,
        base_url=None,
        roles=roles or {"capable": "anthropic/claude-opus-4-6", "fast": "anthropic/claude-sonnet-4-6"},
        auth_type="api_key",
    )


class TestDirectGateway:
    def test_passes_through_unchanged(self):
        provider = _make_provider(GatewayType.DIRECT)
        result = apply_cache_control(MESSAGES_WITH_CACHE, provider)
        assert result is MESSAGES_WITH_CACHE  # same object, no copy

    def test_no_cache_control_no_error(self):
        provider = _make_provider(GatewayType.DIRECT)
        result = apply_cache_control(MESSAGES_WITHOUT_CACHE, provider)
        assert result is MESSAGES_WITHOUT_CACHE


class TestOpenRouterGateway:
    def test_anthropic_models_pass_through(self):
        provider = _make_provider(
            GatewayType.OPENROUTER,
            roles={"capable": "openrouter/anthropic/claude-opus-4-6"},
        )
        result = apply_cache_control(MESSAGES_WITH_CACHE, provider)
        assert result is MESSAGES_WITH_CACHE

    def test_non_anthropic_models_strip_cache(self):
        provider = _make_provider(
            GatewayType.OPENROUTER,
            roles={"capable": "openrouter/mistral/mistral-large"},
        )
        result = apply_cache_control(MESSAGES_WITH_CACHE, provider)
        assert result is not MESSAGES_WITH_CACHE
        assert "cache_control" not in result[0]["content"][0]

    def test_non_anthropic_preserves_other_fields(self):
        provider = _make_provider(
            GatewayType.OPENROUTER,
            roles={"capable": "openrouter/mistral/mistral-large"},
        )
        result = apply_cache_control(MESSAGES_WITH_CACHE, provider)
        assert result[0]["content"][0]["type"] == "text"
        assert result[0]["content"][0]["text"] == "Hello"
        assert result[1]["content"] == "Hi there"


class TestLiteLLMGateway:
    def test_passes_through(self):
        provider = _make_provider(GatewayType.LITELLM)
        result = apply_cache_control(MESSAGES_WITH_CACHE, provider)
        assert result is MESSAGES_WITH_CACHE


class TestStripCacheControl:
    def test_removes_cache_control(self):
        result = _strip_cache_control(MESSAGES_WITH_CACHE)
        assert "cache_control" not in result[0]["content"][0]

    def test_preserves_other_fields(self):
        result = _strip_cache_control(MESSAGES_WITH_CACHE)
        assert result[0]["content"][0]["text"] == "Hello"
        assert result[0]["content"][0]["type"] == "text"

    def test_does_not_mutate_original(self):
        original = copy.deepcopy(MESSAGES_WITH_CACHE)
        _strip_cache_control(MESSAGES_WITH_CACHE)
        assert MESSAGES_WITH_CACHE == original

    def test_string_content_unchanged(self):
        result = _strip_cache_control(MESSAGES_WITHOUT_CACHE)
        assert result[0]["content"] == "Hello"

    def test_mixed_blocks(self):
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "a", "cache_control": {"type": "ephemeral"}},
                    {"type": "text", "text": "b"},
                ],
            }
        ]
        result = _strip_cache_control(messages)
        assert "cache_control" not in result[0]["content"][0]
        assert result[0]["content"][1] == {"type": "text", "text": "b"}
