"""mem0 memory backend adapter.

Wraps mem0 (self-hosted, pgvector) as the memory layer.
Domain isolation enforced via user_id namespacing: {domain}:{operativo_id}.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from mem0 import Memory


@dataclass
class Mem0Config:
    """Configuration for self-hosted mem0 with pgvector."""
    pg_connection_string: str
    collection_name: str
    anthropic_api_key: str | None = None
    embedder_model: str = "voyage-3"
    llm_model: str = "claude-haiku-4-5-20251001"


def build_memory(config: Mem0Config) -> Memory:
    """Build a mem0 Memory instance from config."""
    mem_config: dict = {
        "vector_store": {
            "provider": "pgvector",
            "config": {
                "connection_string": config.pg_connection_string,
                "collection_name": config.collection_name,
            },
        },
    }
    if config.anthropic_api_key:
        mem_config["llm"] = {
            "provider": "anthropic",
            "config": {
                "model": config.llm_model,
                "api_key": config.anthropic_api_key,
            },
        }
    return Memory.from_config(mem_config)


class Mem0DomainMemory:
    """Adapter that delegates to mem0. Domain isolation via user_id."""

    def __init__(self, memory: Memory, domain: str, operativo_id: str) -> None:
        self._mem = memory
        self._domain = domain
        self._user_id = f"{domain}:{operativo_id}"

    @property
    def domain(self) -> str:
        return self._domain

    async def add(self, content: str, metadata: dict | None = None) -> None:
        await asyncio.to_thread(
            self._mem.add, content, user_id=self._user_id, metadata=metadata or {},
        )

    async def search(self, query: str, limit: int = 5) -> list[dict]:
        results = await asyncio.to_thread(
            self._mem.search, query, user_id=self._user_id, limit=limit,
        )
        return results.get("results", []) if isinstance(results, dict) else results
