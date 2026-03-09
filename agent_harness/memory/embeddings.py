"""Embedding client protocol and implementations.

EmbeddingClient is a Protocol — any class with embed/embed_document/embed_query
methods satisfies it. VoyageEmbeddingClient wraps Voyage AI for production.
FakeEmbeddingClient produces deterministic hash-based vectors for tests.
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingClient(Protocol):
    """Protocol for generating text embeddings."""

    async def embed(self, text: str) -> tuple[float, ...]:
        """Generate an embedding vector for the given text."""
        ...

    async def embed_document(self, text: str) -> tuple[float, ...]:
        """Embed a single document for storage."""
        ...

    async def embed_query(self, text: str) -> tuple[float, ...]:
        """Embed a single query for search."""
        ...

    @property
    def dimensions(self) -> int:
        """Return the dimensionality of produced embeddings."""
        ...


class FakeEmbeddingClient:
    """Deterministic hash-based embedding client for testing.

    Produces normalized vectors of fixed dimensionality from text hashes.
    Same text always produces the same embedding.
    """

    def __init__(self, dimensions: int = 64) -> None:
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def _hash_to_vector(self, text: str) -> tuple[float, ...]:
        """Generate a deterministic embedding from text hash."""
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        raw: list[float] = []
        for i in range(self._dimensions):
            byte_idx = i % len(digest)
            raw.append((digest[byte_idx] + i) / 255.0 - 0.5)
        norm = math.sqrt(sum(x * x for x in raw))
        if norm == 0.0:
            return tuple(raw)
        return tuple(x / norm for x in raw)

    async def embed(self, text: str) -> tuple[float, ...]:
        return self._hash_to_vector(text)

    async def embed_document(self, text: str) -> tuple[float, ...]:
        return self._hash_to_vector(text)

    async def embed_query(self, text: str) -> tuple[float, ...]:
        return self._hash_to_vector(text)


class VoyageEmbeddingClient:
    """Wraps Voyage AI SDK for production embedding generation.

    Voyage AI is Anthropic's recommended embedding provider.
    Uses VOYAGE_API_KEY environment variable for authentication.
    """

    def __init__(
        self,
        model: str = "voyage-3-large",
        dimensions: int = 1024,
    ) -> None:
        self._model = model
        self._dimensions = dimensions
        try:
            import voyageai
            self._client = voyageai.Client()
        except ImportError:
            self._client = None

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, text: str) -> tuple[float, ...]:
        """Embed a single text via Voyage AI."""
        result = await self._call_voyage([text], input_type="document")
        return tuple(result[0])

    async def embed_document(self, text: str) -> tuple[float, ...]:
        result = await self._call_voyage([text], input_type="document")
        return tuple(result[0])

    async def embed_query(self, text: str) -> tuple[float, ...]:
        result = await self._call_voyage([text], input_type="query")
        return tuple(result[0])

    async def _call_voyage(
        self, texts: list[str], input_type: str,
    ) -> list[list[float]]:
        """Call Voyage AI sync SDK in thread pool."""
        import asyncio
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._client.embed(
                texts,
                model=self._model,
                input_type=input_type,
                output_dimension=self._dimensions,
            ),
        )
        return result.embeddings
