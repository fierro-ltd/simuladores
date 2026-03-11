"""Tests for DomainRegistry and DomainManifest."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_harness.core.domain_registry import DomainManifest, DomainRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINIMAL_TOML = """\
[domain]
id = "test"
name = "Test Domain"
version = "0.1.0"

[domain.models]
investigator = "claude-opus-4-6"
orchestrator = "claude-opus-4-6"
executor = "claude-sonnet-4-6"
synthesizer = "claude-sonnet-4-6"

[domain.mcp]
server_module = "agent_harness.domains.test.mcp_server"
server_port = 9999

[domain.temporal]
task_queue = "test-operativo"
workflow_id_prefix = "test"

[domain.memory]
collection = "test_domain"

[domain.injection_guard]
semantic_check = true
semantic_threshold = 0.7

[domain.limits]
max_correction_attempts = 3
compaction_threshold = 0.75
"""


def _write_domain(tmp_path: Path, domain_id: str, toml_content: str) -> None:
    domain_dir = tmp_path / domain_id
    domain_dir.mkdir(parents=True, exist_ok=True)
    (domain_dir / "domain.toml").write_text(toml_content)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestLoadManifestFromToml:
    def test_loads_manifest_from_toml(self, tmp_path: Path) -> None:
        _write_domain(tmp_path, "test", MINIMAL_TOML)
        registry = DomainRegistry(tmp_path)

        manifest = registry.get("test")

        assert isinstance(manifest, DomainManifest)
        assert manifest.id == "test"
        assert manifest.name == "Test Domain"
        assert manifest.version == "0.1.0"
        assert manifest.mcp_server_module == "agent_harness.domains.test.mcp_server"
        assert manifest.mcp_server_port == 9999
        assert manifest.temporal_task_queue == "test-operativo"
        assert manifest.workflow_id_prefix == "test"
        assert manifest.memory_collection == "test_domain"
        assert manifest.models["investigator"] == "claude-opus-4-6"
        assert manifest.models["executor"] == "claude-sonnet-4-6"
        assert manifest.injection_guard["semantic_check"] is True
        assert manifest.injection_guard["semantic_threshold"] == 0.7
        assert manifest.limits["max_correction_attempts"] == 3
        assert manifest.limits["compaction_threshold"] == 0.75


class TestUnknownDomainRaises:
    def test_unknown_domain_raises(self, tmp_path: Path) -> None:
        registry = DomainRegistry(tmp_path)
        with pytest.raises(ValueError, match="Unknown domain"):
            registry.get("nonexistent")


class TestListDomains:
    def test_list_domains(self, tmp_path: Path) -> None:
        _write_domain(tmp_path, "alpha", MINIMAL_TOML.replace('id = "test"', 'id = "alpha"'))
        _write_domain(tmp_path, "beta", MINIMAL_TOML.replace('id = "test"', 'id = "beta"'))

        registry = DomainRegistry(tmp_path)
        domains = registry.list_domains()

        assert sorted(domains) == ["alpha", "beta"]


class TestManifestIsFrozen:
    def test_manifest_is_immutable(self, tmp_path: Path) -> None:
        _write_domain(tmp_path, "test", MINIMAL_TOML)
        registry = DomainRegistry(tmp_path)
        manifest = registry.get("test")

        with pytest.raises(AttributeError):
            manifest.id = "hacked"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Integration: loads real domain.toml files from agent_harness/domains/
# ---------------------------------------------------------------------------

DOMAINS_ROOT = Path(__file__).resolve().parents[2] / "agent_harness" / "domains"


class TestRealDomains:
    @pytest.mark.skipif(
        not (DOMAINS_ROOT / "dce" / "domain.toml").exists(),
        reason="domain.toml files not yet created",
    )
    def test_loads_real_domains(self) -> None:
        registry = DomainRegistry(DOMAINS_ROOT)
        domains = registry.list_domains()

        assert "dce" in domains
        assert "idp" in domains
        assert "has" in domains

        dce = registry.get("dce")
        assert dce.temporal_task_queue == "dce-operativo"
        assert dce.mcp_server_port == 8001

        idp = registry.get("idp")
        assert idp.temporal_task_queue == "idp-operativo"
        assert idp.mcp_server_port == 8002

        has = registry.get("has")
        assert has.temporal_task_queue == "has-operativo"
        assert has.mcp_server_port == 8003
