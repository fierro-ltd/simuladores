"""Tests for VoyageEmbeddingClient with mocked SDK."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_harness.memory.embeddings import VoyageEmbeddingClient


class TestVoyageEmbeddingClient:
    @pytest.mark.asyncio
    async def test_embed_calls_voyage_sdk(self):
        mock_result = MagicMock()
        mock_result.embeddings = [[0.1, 0.2, 0.3, 0.4]]

        client = VoyageEmbeddingClient(model="voyage-4", dimensions=4)
        client._client = MagicMock()

        with patch("asyncio.get_running_loop") as mock_loop:
            future = AsyncMock(return_value=mock_result)
            mock_loop.return_value.run_in_executor = future
            vec = await client.embed("hello")

        assert isinstance(vec, tuple)
        assert len(vec) == 4

    @pytest.mark.asyncio
    async def test_embed_document_delegates(self):
        mock_result = MagicMock()
        mock_result.embeddings = [[0.5, 0.6]]

        client = VoyageEmbeddingClient(model="voyage-4", dimensions=2)
        client._client = MagicMock()

        with patch("asyncio.get_running_loop") as mock_loop:
            future = AsyncMock(return_value=mock_result)
            mock_loop.return_value.run_in_executor = future
            vec = await client.embed_document("test doc")

        assert isinstance(vec, tuple)
        assert vec == (0.5, 0.6)

    @pytest.mark.asyncio
    async def test_embed_query_uses_query_input_type(self):
        mock_result = MagicMock()
        mock_result.embeddings = [[0.9, 0.8]]

        client = VoyageEmbeddingClient(model="voyage-4", dimensions=2)
        client._client = MagicMock()

        with patch("asyncio.get_running_loop") as mock_loop:
            future = AsyncMock(return_value=mock_result)
            mock_loop.return_value.run_in_executor = future
            vec = await client.embed_query("test query")

        assert isinstance(vec, tuple)
        assert vec == (0.9, 0.8)

    def test_default_model_and_dimensions(self):
        client = VoyageEmbeddingClient()
        assert client._model == "voyage-3-large"
        assert client._dimensions == 1024
