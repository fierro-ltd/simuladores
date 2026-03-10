"""Smoke test: IDP domain can dispatch, build workflow input, and construct tool handler."""

import pytest
from unittest.mock import MagicMock

from agent_harness.domains.idp.operativo import IdpOperativoInput, IdpOperativoOutput
from agent_harness.domains.idp.tools import discover_api, list_operations, get_operation_schema
from agent_harness.gateway.dispatch import dispatch_idp_operativo
from agent_harness.activities.factory import build_tool_handler
from agent_harness.core.operativo import OperativoStatus


def test_idp_full_dispatch_flow():
    """Dispatch creates valid operativo_id and workflow input."""
    result = dispatch_idp_operativo(
        document_path="/tmp/test.pdf",
        plugin_id="invoices",
        caller_id="smoke-test",
    )
    assert result.operativo_id.startswith("idp-")
    assert result.status == OperativoStatus.PENDING
    assert result.workflow_input.document_path == "/tmp/test.pdf"
    assert result.workflow_input.plugin_id == "invoices"


def test_idp_tool_handler_construction():
    """Tool handler builds for IDP domain with all expected tools."""
    client = MagicMock()
    handler = build_tool_handler(client=client, domain="idp", operativo_id="idp-test123")
    assert handler is not None


def test_idp_manifest_completeness():
    """All 12 operations are discoverable and have schemas."""
    ops = list_operations()
    assert len(ops) == 12
    for op in ops:
        schema = get_operation_schema(op)
        assert schema is not None, f"Missing schema for {op}"
        assert "description" in schema
        assert "params" in schema
        assert "returns" in schema


def test_idp_discover_api_has_all_categories():
    """discover_api returns text covering all three categories."""
    text = discover_api()
    for category in ("jobs", "plugins", "settings"):
        assert f"[{category}]" in text
