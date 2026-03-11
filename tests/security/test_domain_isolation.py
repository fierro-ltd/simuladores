"""Tests for domain isolation enforcement."""

import pytest

from agent_harness.core.registry import OperativoRegistry
from agent_harness.core.permissions import (
    GLOBAL_DENY_LIST,
)
from agent_harness.domains.dce.tools import list_operations as cpc_ops
from agent_harness.domains.has.tools import list_operations as cee_ops
from agent_harness.domains.idp.tools import list_operations as nav_ops
from agent_harness.gateway.router import build_default_registry


class TestDomainToolIsolation:
    """Verify domains have non-overlapping tool sets."""

    def test_cpc_and_cee_no_overlap(self):
        dce = set(cpc_ops())
        has = set(cee_ops())
        overlap = dce & has
        assert overlap == set(), f"DCE and HAS share tools: {overlap}"

    def test_cpc_and_navigator_no_overlap(self):
        dce = set(cpc_ops())
        nav = set(nav_ops())
        overlap = dce & nav
        assert overlap == set(), f"DCE and IDP share tools: {overlap}"

    def test_cee_and_navigator_no_overlap(self):
        has = set(cee_ops())
        nav = set(nav_ops())
        overlap = has & nav
        assert overlap == set(), f"HAS and IDP share tools: {overlap}"


class TestDomainRegistryIsolation:
    """Verify registry enforces unique task queues."""

    def test_unique_task_queues(self):
        registry = build_default_registry()
        queues = [registry.get(d).task_queue for d in registry.domains]
        assert len(queues) == len(set(queues))

    def test_unique_workflow_names(self):
        registry = build_default_registry()
        names = [registry.get(d).workflow_name for d in registry.domains]
        assert len(names) == len(set(names))

    def test_duplicate_registration_fails(self):
        registry = OperativoRegistry()
        registry.register("dce", "dce-q", "CPCWorkflow")
        with pytest.raises(ValueError, match="already registered"):
            registry.register("dce", "dce-q2", "CPCWorkflow2")


class TestGlobalDenyList:
    """Verify global deny list blocks dangerous tools."""

    def test_deny_list_not_empty(self):
        assert len(GLOBAL_DENY_LIST) > 0

    def test_shell_exec_denied(self):
        assert "shell_exec" in GLOBAL_DENY_LIST

    def test_http_request_denied(self):
        assert "http_request" in GLOBAL_DENY_LIST

    def test_filesystem_write_denied(self):
        assert "filesystem_write" in GLOBAL_DENY_LIST

    def test_no_domain_tool_in_deny_list(self):
        all_domain_tools = set(cpc_ops()) | set(cee_ops()) | set(nav_ops())
        denied_domain = all_domain_tools & set(GLOBAL_DENY_LIST)
        assert denied_domain == set(), f"Domain tools in deny list: {denied_domain}"
