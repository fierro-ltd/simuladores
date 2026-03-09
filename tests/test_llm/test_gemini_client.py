"""Tests for GeminiClient."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_harness.llm.gemini_client import GeminiClient, GeminiVisionResult


class TestGeminiVisionResult:
    """Tests for GeminiVisionResult dataclass."""

    def test_creation(self):
        result = GeminiVisionResult(text="hello", page_number=1, model="gemini-2.0-flash")
        assert result.text == "hello"
        assert result.page_number == 1

    def test_defaults(self):
        result = GeminiVisionResult(text="hello", page_number=1)
        assert result.model == ""


class TestGeminiClientInit:
    """Tests for GeminiClient initialization."""

    def test_from_env(self):
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "env-proj"}):
            with patch("agent_harness.llm.gemini_client.genai") as mock:
                client = GeminiClient()
                mock.Client.assert_called_once_with(
                    vertexai=True, project="env-proj", location="us-central1"
                )

    def test_explicit_params(self):
        with patch("agent_harness.llm.gemini_client.genai") as mock:
            client = GeminiClient(project_id="p", region="eu-west1", model="gemini-3-flash")
            mock.Client.assert_called_once_with(
                vertexai=True, project="p", location="eu-west1"
            )

    def test_default_model(self):
        with patch("agent_harness.llm.gemini_client.genai"):
            client = GeminiClient(project_id="p")
            assert client._model == "gemini-2.0-flash"


class TestGeminiClientExtract:
    """Tests for extract_from_image method."""

    @pytest.mark.asyncio
    async def test_sends_image_and_prompt(self):
        with patch("agent_harness.llm.gemini_client.genai") as mock_genai:
            mock_response = MagicMock()
            mock_response.text = "extracted text"
            mock_generate = AsyncMock(return_value=mock_response)
            mock_genai.Client.return_value.aio.models.generate_content = mock_generate

            client = GeminiClient(project_id="test")
            result = await client.extract_from_image(b"png-bytes", "Extract")

            assert result == "extracted text"
            mock_generate.assert_called_once()
            call_kwargs = mock_generate.call_args
            assert call_kwargs.kwargs["model"] == "gemini-2.0-flash"

    @pytest.mark.asyncio
    async def test_empty_response(self):
        with patch("agent_harness.llm.gemini_client.genai") as mock_genai:
            mock_response = MagicMock()
            mock_response.text = None
            mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(
                return_value=mock_response
            )

            client = GeminiClient(project_id="test")
            result = await client.extract_from_image(b"png-bytes", "Extract")
            assert result == ""
