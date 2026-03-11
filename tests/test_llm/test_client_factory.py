"""Tests for the provider-aware LLM client factory."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agent_harness.core.provider_config import GatewayType, ProviderConfig


def _make_provider(
    gateway: GatewayType,
    roles: dict[str, str] | None = None,
    base_url: str | None = None,
) -> ProviderConfig:
    return ProviderConfig(
        name="test",
        gateway=gateway,
        base_url=base_url,
        roles=roles or {"planner": "claude-opus-4-20250514", "executor": "claude-sonnet-4-20250514"},
        auth_type="gcp-adc" if gateway == GatewayType.DIRECT else "api-key",
    )


class TestDirectGateway:
    @patch("agent_harness.llm.client_factory.instructor")
    @patch("anthropic.AsyncAnthropicVertex")
    def test_returns_instructor_client_and_model(
        self, mock_vertex_cls, mock_instructor
    ):
        mock_vertex_cls.return_value = MagicMock()
        mock_instructor.from_anthropic.return_value = MagicMock()

        from agent_harness.llm.client_factory import build_instructor_client

        provider = _make_provider(GatewayType.DIRECT)
        client, model, retries = build_instructor_client(provider, "planner")

        assert model == "claude-opus-4-20250514"
        assert retries == 2
        mock_vertex_cls.assert_called_once()
        mock_instructor.from_anthropic.assert_called_once()

    @patch("agent_harness.llm.client_factory.instructor")
    @patch("anthropic.AsyncAnthropicVertex")
    def test_max_retries_is_2(self, mock_vertex_cls, mock_instructor):
        mock_vertex_cls.return_value = MagicMock()
        mock_instructor.from_anthropic.return_value = MagicMock()

        from agent_harness.llm.client_factory import build_instructor_client

        provider = _make_provider(GatewayType.DIRECT)
        _, _, retries = build_instructor_client(provider, "executor")
        assert retries == 2


class TestOpenRouterGateway:
    @patch("agent_harness.llm.client_factory.instructor")
    @patch("openai.AsyncOpenAI")
    def test_returns_instructor_client_and_model(
        self, mock_openai_cls, mock_instructor
    ):
        mock_openai_cls.return_value = MagicMock()
        mock_instructor.from_openai.return_value = MagicMock()
        mock_instructor.Mode.JSON = "json"

        from agent_harness.llm.client_factory import build_instructor_client

        provider = _make_provider(
            GatewayType.OPENROUTER,
            roles={"planner": "anthropic/claude-opus-4-20250514"},
        )
        client, model, retries = build_instructor_client(provider, "planner")

        assert model == "anthropic/claude-opus-4-20250514"
        assert retries == 3
        mock_openai_cls.assert_called_once()
        call_kwargs = mock_openai_cls.call_args[1]
        assert call_kwargs["base_url"] == "https://openrouter.ai/api/v1"
        assert call_kwargs["default_headers"]["HTTP-Referer"] == "https://fierro.co.uk"
        assert call_kwargs["default_headers"]["X-Title"] == "Simuladores"
        mock_instructor.from_openai.assert_called_once()

    @patch("agent_harness.llm.client_factory.instructor")
    @patch("openai.AsyncOpenAI")
    def test_max_retries_is_3(self, mock_openai_cls, mock_instructor):
        mock_openai_cls.return_value = MagicMock()
        mock_instructor.from_openai.return_value = MagicMock()
        mock_instructor.Mode.JSON = "json"

        from agent_harness.llm.client_factory import build_instructor_client

        provider = _make_provider(
            GatewayType.OPENROUTER,
            roles={"planner": "anthropic/claude-opus-4-20250514"},
        )
        _, _, retries = build_instructor_client(provider, "planner")
        assert retries == 3


class TestLiteLLMGateway:
    @patch("agent_harness.llm.client_factory.instructor")
    @patch("openai.AsyncOpenAI")
    def test_returns_instructor_client_and_model(
        self, mock_openai_cls, mock_instructor
    ):
        mock_openai_cls.return_value = MagicMock()
        mock_instructor.from_openai.return_value = MagicMock()
        mock_instructor.Mode.JSON = "json"

        from agent_harness.llm.client_factory import build_instructor_client

        provider = _make_provider(
            GatewayType.LITELLM,
            roles={"planner": "anthropic/claude-opus-4-20250514"},
            base_url="http://localhost:4000",
        )
        client, model, retries = build_instructor_client(provider, "planner")

        assert model == "anthropic/claude-opus-4-20250514"
        assert retries == 3
        mock_openai_cls.assert_called_once()
        mock_instructor.from_openai.assert_called_once()

    @patch("agent_harness.llm.client_factory.instructor")
    @patch("openai.AsyncOpenAI")
    def test_uses_provider_base_url(self, mock_openai_cls, mock_instructor):
        mock_openai_cls.return_value = MagicMock()
        mock_instructor.from_openai.return_value = MagicMock()
        mock_instructor.Mode.JSON = "json"

        from agent_harness.llm.client_factory import build_instructor_client

        provider = _make_provider(
            GatewayType.LITELLM,
            roles={"planner": "anthropic/claude-opus-4-20250514"},
            base_url="http://my-proxy:8080",
        )
        build_instructor_client(provider, "planner")

        call_kwargs = mock_openai_cls.call_args[1]
        assert call_kwargs["base_url"] == "http://my-proxy:8080"

    @patch("agent_harness.llm.client_factory.instructor")
    @patch("openai.AsyncOpenAI")
    def test_max_retries_is_3(self, mock_openai_cls, mock_instructor):
        mock_openai_cls.return_value = MagicMock()
        mock_instructor.from_openai.return_value = MagicMock()
        mock_instructor.Mode.JSON = "json"

        from agent_harness.llm.client_factory import build_instructor_client

        provider = _make_provider(
            GatewayType.LITELLM,
            roles={"planner": "x"},
            base_url="http://localhost:4000",
        )
        _, _, retries = build_instructor_client(provider, "planner")
        assert retries == 3


class TestInvalidRole:
    def test_invalid_role_raises_value_error(self):
        from agent_harness.llm.client_factory import build_instructor_client

        provider = _make_provider(GatewayType.DIRECT, roles={"planner": "model-x"})
        with pytest.raises(ValueError, match="Role 'nonexistent' not defined"):
            build_instructor_client(provider, "nonexistent")
