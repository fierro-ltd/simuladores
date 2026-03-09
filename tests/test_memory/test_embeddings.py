"""Tests for embedding client."""

import math

import pytest

from agent_harness.memory.embeddings import EmbeddingClient, FakeEmbeddingClient


class TestFakeEmbeddingClient:
    @pytest.fixture
    def client(self):
        return FakeEmbeddingClient(dimensions=64)

    @pytest.mark.asyncio
    async def test_implements_protocol(self, client):
        assert isinstance(client, EmbeddingClient)

    @pytest.mark.asyncio
    async def test_returns_correct_dimensions(self, client):
        vec = await client.embed("hello")
        assert len(vec) == 64

    @pytest.mark.asyncio
    async def test_deterministic(self, client):
        a = await client.embed("test input")
        b = await client.embed("test input")
        assert a == b

    @pytest.mark.asyncio
    async def test_different_text_different_embedding(self, client):
        a = await client.embed("hello")
        b = await client.embed("world")
        assert a != b

    @pytest.mark.asyncio
    async def test_normalized(self, client):
        vec = await client.embed("test")
        norm = math.sqrt(sum(x * x for x in vec))
        assert abs(norm - 1.0) < 1e-6

    def test_dimensions_property(self, client):
        assert client.dimensions == 64

    @pytest.mark.asyncio
    async def test_custom_dimensions(self):
        client = FakeEmbeddingClient(dimensions=128)
        vec = await client.embed("test")
        assert len(vec) == 128
        assert client.dimensions == 128
