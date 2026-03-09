"""Tests for operativo registry."""

import pytest

from agent_harness.core.registry import OperativoRegistry, RegistryEntry


class TestRegistryEntry:
    def test_frozen(self):
        entry = RegistryEntry(domain="dce", task_queue="dce-queue", workflow_name="dce-workflow")
        with pytest.raises(AttributeError):
            entry.domain = "other"  # type: ignore[misc]


class TestOperativoRegistry:
    def test_register_and_get(self):
        reg = OperativoRegistry()
        reg.register("dce", "dce-queue", "dce-workflow")
        entry = reg.get("dce")
        assert entry.domain == "dce"
        assert entry.task_queue == "dce-queue"
        assert entry.workflow_name == "dce-workflow"

    def test_duplicate_raises(self):
        reg = OperativoRegistry()
        reg.register("dce", "dce-queue", "dce-workflow")
        with pytest.raises(ValueError, match="already registered"):
            reg.register("dce", "dce-queue2", "dce-workflow2")

    def test_unknown_domain_raises(self):
        reg = OperativoRegistry()
        with pytest.raises(KeyError, match="not registered"):
            reg.get("unknown")

    def test_domains_property(self):
        reg = OperativoRegistry()
        reg.register("dce", "dce-queue", "dce-workflow")
        reg.register("has", "has-queue", "has-workflow")
        assert reg.domains == frozenset({"dce", "has"})

    def test_empty_domains(self):
        reg = OperativoRegistry()
        assert reg.domains == frozenset()
