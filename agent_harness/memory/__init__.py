"""Memory stores: domain, session, semantic, and structured graph."""

from agent_harness.memory.bulletin import Bulletin, BulletinConfig, generate_bulletin
from agent_harness.memory.bulletin_store import InMemoryBulletinStore
from agent_harness.memory.domain_store import DomainStore, DomainWriteAttemptError
from agent_harness.memory.embeddings import (
    EmbeddingClient,
    FakeEmbeddingClient,
    VoyageEmbeddingClient,
)
from agent_harness.memory.graph import (
    MemoryEdge,
    MemoryNode,
    MemoryType,
    RelationType,
)
from agent_harness.memory.graph_store import InMemoryGraphStore
from agent_harness.memory.mem0_backend import Mem0Config, Mem0DomainMemory, build_memory
from agent_harness.memory.recall import MemoryRecall
from agent_harness.memory.semantic_store import Pattern, SemanticStore
from agent_harness.memory.session_store import SessionStore

__all__ = [
    # Bulletin (Cortex)
    "Bulletin",
    "BulletinConfig",
    "generate_bulletin",
    "InMemoryBulletinStore",
    # Domain store
    "DomainStore",
    "DomainWriteAttemptError",
    # Legacy semantic store (backward compat)
    "Pattern",
    "SemanticStore",
    # Session store
    "SessionStore",
    # Graph types
    "MemoryType",
    "RelationType",
    "MemoryNode",
    "MemoryEdge",
    # Embeddings
    "EmbeddingClient",
    "FakeEmbeddingClient",
    "VoyageEmbeddingClient",
    # Graph store
    "InMemoryGraphStore",
    # Recall
    "MemoryRecall",
    # mem0 backend
    "Mem0Config",
    "Mem0DomainMemory",
    "build_memory",
]
