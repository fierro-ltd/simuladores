"""Tests for permissions and policy chain."""

import pytest

from agent_harness.core.permissions import (
    GLOBAL_DENY_LIST,
    PermissionLevel,
    PolicyChain,
    ToolDeniedError,
    ToolPolicy,
)


class TestPermissionLevel:
    def test_levels_exist(self):
        assert PermissionLevel.AUTO == "AUTO"
        assert PermissionLevel.SESSION == "SESSION"
        assert PermissionLevel.HUMAN_APPROVAL == "HUMAN_APPROVAL"


class TestGlobalDenyList:
    def test_contains_dangerous_tools(self):
        assert "shell_exec" in GLOBAL_DENY_LIST
        assert "http_request" in GLOBAL_DENY_LIST
        assert "filesystem_write" in GLOBAL_DENY_LIST
        assert "os_exec" in GLOBAL_DENY_LIST
        assert "subprocess" in GLOBAL_DENY_LIST


class TestPolicyChain:
    def test_global_deny_blocks(self):
        chain = PolicyChain(domain="dce", domain_tools=frozenset({"read_pdf"}))
        with pytest.raises(ToolDeniedError):
            chain.check("shell_exec", agent="lamponne")

    def test_domain_allowlist_permits(self):
        chain = PolicyChain(domain="dce", domain_tools=frozenset({"read_pdf"}))
        result = chain.check("read_pdf", agent="medina")
        assert result.permitted is True
        assert result.requires_sandbox is False

    def test_domain_allowlist_blocks_unknown(self):
        chain = PolicyChain(domain="dce", domain_tools=frozenset({"read_pdf"}))
        with pytest.raises(ToolDeniedError):
            chain.check("unknown_tool", agent="lamponne")

    def test_sandbox_routing(self):
        chain = PolicyChain(domain="dce", domain_tools=frozenset({"read_pdf"}))
        result = chain.check("run_python_sandbox", agent="lamponne")
        assert result.permitted is True
        assert result.requires_sandbox is True

    def test_global_deny_takes_precedence(self):
        chain = PolicyChain(domain="dce", domain_tools=frozenset({"shell_exec"}))
        with pytest.raises(ToolDeniedError):
            chain.check("shell_exec", agent="lamponne")


class TestToolPolicy:
    def test_creation(self):
        policy = ToolPolicy(name="read_pdf", permission=PermissionLevel.AUTO)
        assert policy.name == "read_pdf"
        assert policy.permission == PermissionLevel.AUTO
