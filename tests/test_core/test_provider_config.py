"""Tests for provider configuration loader."""

from __future__ import annotations

import os

import pytest

from agent_harness.core.provider_config import (
    GatewayType,
    ProviderConfig,
    load_provider_config,
)


# ---------------------------------------------------------------------------
# Happy-path loading
# ---------------------------------------------------------------------------


class TestLoadAnthropicVertex:
    def test_loads_successfully(self):
        cfg = load_provider_config("anthropic-vertex")
        assert isinstance(cfg, ProviderConfig)

    def test_name(self):
        cfg = load_provider_config("anthropic-vertex")
        assert cfg.name == "anthropic-vertex"

    def test_gateway(self):
        cfg = load_provider_config("anthropic-vertex")
        assert cfg.gateway is GatewayType.DIRECT

    def test_base_url_is_none(self):
        cfg = load_provider_config("anthropic-vertex")
        assert cfg.base_url is None

    def test_auth_type(self):
        cfg = load_provider_config("anthropic-vertex")
        assert cfg.auth_type == "vertex"

    def test_roles(self):
        cfg = load_provider_config("anthropic-vertex")
        assert cfg.roles["capable"] == "anthropic/claude-opus-4-6"
        assert cfg.roles["fast"] == "anthropic/claude-sonnet-4-6"
        assert cfg.roles["extract"] == "anthropic/claude-haiku-4-5-20251001"
        assert cfg.roles["local"] == "anthropic/claude-haiku-4-5-20251001"


class TestLoadOpenRouter:
    def test_loads_successfully(self):
        cfg = load_provider_config("openrouter")
        assert cfg.name == "openrouter"
        assert cfg.gateway is GatewayType.OPENROUTER
        assert cfg.base_url == "https://openrouter.ai/api/v1"
        assert cfg.auth_type == "api_key"
        assert cfg.roles["capable"] == "openrouter/anthropic/claude-opus-4-6"


class TestLoadLitellmProxy:
    def test_loads_successfully(self):
        cfg = load_provider_config("litellm-proxy")
        assert cfg.name == "litellm-proxy"
        assert cfg.gateway is GatewayType.LITELLM
        assert cfg.base_url == "http://litellm-proxy:4000"
        assert cfg.auth_type == "api_key"
        assert cfg.roles["capable"] == "simuladores-capable"


class TestLoadHospitalAirgapped:
    def test_loads_successfully(self):
        cfg = load_provider_config("hospital-airgapped")
        assert cfg.name == "hospital-airgapped"
        assert cfg.gateway is GatewayType.LITELLM
        assert cfg.base_url == "http://litellm-proxy:4000"
        assert cfg.roles["fast"] == "simuladores-fast"


class TestLoadLocalOllama:
    def test_loads_successfully(self):
        cfg = load_provider_config("local-ollama")
        assert cfg.name == "local-ollama"
        assert cfg.gateway is GatewayType.LITELLM
        assert cfg.base_url == "http://localhost:4000"
        assert cfg.auth_type == "api_key"
        assert cfg.roles["capable"] == "simuladores-capable"
        assert cfg.roles["fast"] == "simuladores-fast"


# ---------------------------------------------------------------------------
# resolve_model
# ---------------------------------------------------------------------------


class TestResolveModel:
    def test_resolves_known_role(self):
        cfg = load_provider_config("anthropic-vertex")
        assert cfg.resolve_model("capable") == "anthropic/claude-opus-4-6"

    def test_resolves_all_roles(self):
        cfg = load_provider_config("anthropic-vertex")
        for role in ("capable", "fast", "extract", "local"):
            result = cfg.resolve_model(role)
            assert isinstance(result, str)
            assert len(result) > 0

    def test_unknown_role_raises_value_error(self):
        cfg = load_provider_config("anthropic-vertex")
        with pytest.raises(ValueError, match="nonexistent"):
            cfg.resolve_model("nonexistent")


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestErrorCases:
    def test_nonexistent_profile_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="nonexistent-profile"):
            load_provider_config("nonexistent-profile")

    def test_file_not_found_lists_available(self):
        with pytest.raises(FileNotFoundError, match="anthropic-vertex"):
            load_provider_config("nonexistent-profile")


# ---------------------------------------------------------------------------
# Default / env var behaviour
# ---------------------------------------------------------------------------


class TestDefaultProfile:
    def test_default_is_anthropic_vertex(self, monkeypatch):
        monkeypatch.delenv("SIMULADORES_PROVIDER_PROFILE", raising=False)
        cfg = load_provider_config()
        assert cfg.name == "anthropic-vertex"

    def test_env_var_overrides_default(self, monkeypatch):
        monkeypatch.setenv("SIMULADORES_PROVIDER_PROFILE", "openrouter")
        cfg = load_provider_config()
        assert cfg.name == "openrouter"

    def test_explicit_arg_overrides_env_var(self, monkeypatch):
        monkeypatch.setenv("SIMULADORES_PROVIDER_PROFILE", "openrouter")
        cfg = load_provider_config("anthropic-vertex")
        assert cfg.name == "anthropic-vertex"


# ---------------------------------------------------------------------------
# GatewayType enum coverage
# ---------------------------------------------------------------------------


class TestGatewayType:
    def test_all_values(self):
        assert set(GatewayType) == {
            GatewayType.DIRECT,
            GatewayType.OPENROUTER,
            GatewayType.LITELLM,
        }

    def test_string_values(self):
        assert GatewayType.DIRECT.value == "direct"
        assert GatewayType.OPENROUTER.value == "openrouter"
        assert GatewayType.LITELLM.value == "litellm"

    def test_str_enum(self):
        # GatewayType is a str enum — can be compared to plain strings
        assert GatewayType.DIRECT == "direct"


# ---------------------------------------------------------------------------
# Frozen dataclass
# ---------------------------------------------------------------------------


class TestProviderConfigImmutable:
    def test_frozen(self):
        cfg = load_provider_config("anthropic-vertex")
        with pytest.raises(AttributeError):
            cfg.name = "something-else"  # type: ignore[misc]
