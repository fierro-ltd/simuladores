"""Memory recall: bridges graph store to PromptBuilder's list[str] format.

MemoryRecall takes a query, searches the graph store, and returns formatted
strings suitable for PromptBuilder.set_semantic_patterns().
"""

from __future__ import annotations

from agent_harness.memory.graph import MemoryNode, MemoryType
from agent_harness.memory.graph_store import InMemoryGraphStore


class MemoryRecall:
    """Bridges memory graph store to the prompt builder's L3 layer.

    Searches the graph store and formats results as the list[str]
    expected by PromptBuilder.set_semantic_patterns().
    """

    def __init__(self, store: InMemoryGraphStore) -> None:
        self.store = store

    async def retrieve_patterns(
        self,
        domain: str,
        query: str,
        top_k: int = 5,
        memory_types: list[MemoryType] | None = None,
    ) -> list[str]:
        """Retrieve patterns as formatted strings for PromptBuilder L3.

        Returns list of strings like "[fact] Toys require ASTM F963 testing."
        """
        nodes = await self.store.search(
            domain,
            query,
            match_count=top_k,
            memory_types=memory_types,
        )
        return [self._format_node(n) for n in nodes]

    @staticmethod
    def _format_node(node: MemoryNode) -> str:
        """Format a node for prompt injection."""
        return f"[{node.memory_type.value}] {node.content}"
