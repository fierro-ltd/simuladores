"""Tests for mem0 memory backend adapter."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from agent_harness.memory.mem0_backend import Mem0Config, Mem0DomainMemory, build_memory


# ---------------------------------------------------------------------------
# Mem0Config defaults
# ---------------------------------------------------------------------------

def test_mem0_config_defaults():
    cfg = Mem0Config(
        pg_connection_string="postgresql://u:p@localhost/db",
        collection_name="test_col",
    )
    assert cfg.anthropic_api_key is None
    assert cfg.embedder_model == "voyage-3"
    assert cfg.llm_model == "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# build_memory
# ---------------------------------------------------------------------------

@patch("agent_harness.memory.mem0_backend.Memory")
def test_build_memory_returns_memory_instance(mock_memory_cls):
    sentinel = MagicMock()
    mock_memory_cls.from_config.return_value = sentinel

    cfg = Mem0Config(
        pg_connection_string="postgresql://u:p@localhost/db",
        collection_name="test_col",
    )
    result = build_memory(cfg)

    assert result is sentinel
    mock_memory_cls.from_config.assert_called_once()
    call_args = mock_memory_cls.from_config.call_args[0][0]
    assert call_args["vector_store"]["provider"] == "pgvector"
    assert call_args["vector_store"]["config"]["collection_name"] == "test_col"
    # No LLM section when no API key
    assert "llm" not in call_args


@patch("agent_harness.memory.mem0_backend.Memory")
def test_build_memory_with_anthropic_key(mock_memory_cls):
    cfg = Mem0Config(
        pg_connection_string="postgresql://u:p@localhost/db",
        collection_name="col",
        anthropic_api_key="sk-test",
    )
    build_memory(cfg)
    call_args = mock_memory_cls.from_config.call_args[0][0]
    assert call_args["llm"]["provider"] == "anthropic"
    assert call_args["llm"]["config"]["api_key"] == "sk-test"


# ---------------------------------------------------------------------------
# Mem0DomainMemory.add
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mem0_domain_memory_add():
    mock_mem = MagicMock()
    adapter = Mem0DomainMemory(memory=mock_mem, domain="dce", operativo_id="op-1")

    await adapter.add("some content", metadata={"key": "val"})

    mock_mem.add.assert_called_once_with(
        "some content", user_id="dce:op-1", metadata={"key": "val"},
    )


@pytest.mark.asyncio
async def test_mem0_domain_memory_add_default_metadata():
    mock_mem = MagicMock()
    adapter = Mem0DomainMemory(memory=mock_mem, domain="dce", operativo_id="op-2")

    await adapter.add("content")

    mock_mem.add.assert_called_once_with(
        "content", user_id="dce:op-2", metadata={},
    )


# ---------------------------------------------------------------------------
# Mem0DomainMemory.search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mem0_domain_memory_search_dict_results():
    mock_mem = MagicMock()
    mock_mem.search.return_value = {"results": [{"memory": "pattern-A"}]}
    adapter = Mem0DomainMemory(memory=mock_mem, domain="dce", operativo_id="op-1")

    results = await adapter.search("compliance", limit=3)

    assert results == [{"memory": "pattern-A"}]
    mock_mem.search.assert_called_once_with(
        "compliance", user_id="dce:op-1", limit=3,
    )


@pytest.mark.asyncio
async def test_mem0_domain_memory_search_list_results():
    mock_mem = MagicMock()
    mock_mem.search.return_value = [{"memory": "pattern-B"}]
    adapter = Mem0DomainMemory(memory=mock_mem, domain="idp", operativo_id="op-5")

    results = await adapter.search("extraction")

    assert results == [{"memory": "pattern-B"}]


# ---------------------------------------------------------------------------
# Domain isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mem0_domain_isolation():
    mock_mem = MagicMock()
    dce = Mem0DomainMemory(memory=mock_mem, domain="dce", operativo_id="op-1")
    idp = Mem0DomainMemory(memory=mock_mem, domain="idp", operativo_id="op-1")

    assert dce._user_id == "dce:op-1"
    assert idp._user_id == "idp:op-1"
    assert dce._user_id != idp._user_id
    assert dce.domain == "dce"
    assert idp.domain == "idp"

    await dce.add("dce content")
    await idp.add("idp content")

    calls = mock_mem.add.call_args_list
    assert calls[0].kwargs.get("user_id") or calls[0][1]["user_id"] == "dce:op-1"
    assert calls[1].kwargs.get("user_id") or calls[1][1]["user_id"] == "idp:op-1"
