"""Tests for agent provider integration — backward compat and provider-aware construction."""
from __future__ import annotations

from agent_harness.agents.base import AgentConfig, BaseAgent
from agent_harness.agents.medina import MedinaInvestigator
from agent_harness.agents.lamponne import LamponneExecutor
from agent_harness.agents.ravenna import RavennaSynthesizer
from agent_harness.agents.santos import SantosPlanner
from agent_harness.core.provider_config import GatewayType, ProviderConfig


def _make_provider() -> ProviderConfig:
    return ProviderConfig(
        name="test",
        gateway=GatewayType.DIRECT,
        base_url=None,
        roles={"capable": "test-opus", "fast": "test-sonnet"},
        auth_type="vertex",
    )


class TestSantosProviderIntegration:
    def test_backward_compat_no_provider(self):
        cfg = AgentConfig(name="santos", model="m", system_identity="id", domain="dce")
        planner = SantosPlanner(BaseAgent(cfg))
        assert planner._provider is None

    def test_with_provider(self):
        cfg = AgentConfig(name="santos", model="m", system_identity="id", domain="dce")
        planner = SantosPlanner(BaseAgent(cfg), provider=_make_provider())
        assert planner._provider is not None


class TestMedinaProviderIntegration:
    def test_backward_compat_no_provider(self):
        m = MedinaInvestigator(domain="dce")
        assert m.config.model == "claude-sonnet-4-6"  # default from AGENT_MODELS

    def test_with_provider(self):
        m = MedinaInvestigator(domain="dce", provider=_make_provider())
        assert m.config.model == "test-opus"  # capable role


class TestLamponneProviderIntegration:
    def test_backward_compat_no_provider(self):
        l = LamponneExecutor(domain="dce")
        assert l.config.model == "claude-sonnet-4-6"

    def test_with_provider(self):
        l = LamponneExecutor(domain="dce", provider=_make_provider())
        assert l.config.model == "test-sonnet"  # fast role


class TestRavennaProviderIntegration:
    def test_backward_compat_no_provider(self):
        r = RavennaSynthesizer(domain="dce")
        assert r.config.model == "claude-sonnet-4-6"

    def test_with_provider(self):
        r = RavennaSynthesizer(domain="dce", provider=_make_provider())
        assert r.config.model == "test-sonnet"  # fast role
