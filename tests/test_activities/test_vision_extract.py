"""Tests for Gemini vision extraction activity."""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_harness.activities.vision_extract import (
    VISION_EXTRACTION_PROMPT,
    VisionExtractInput,
    VisionExtractOutput,
    gemini_vision_extract,
)
from agent_harness.llm.gemini_client import GeminiClient


class TestGeminiClient:
    """Tests for GeminiClient."""

    def test_init_defaults(self):
        """Client initializes with env var project ID."""
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"}):
            with patch("agent_harness.llm.gemini_client.genai") as mock_genai:
                client = GeminiClient()
                mock_genai.Client.assert_called_once_with(
                    vertexai=True,
                    project="test-project",
                    location="us-central1",
                )

    def test_init_explicit_params(self):
        """Client accepts explicit project and region."""
        with patch("agent_harness.llm.gemini_client.genai") as mock_genai:
            client = GeminiClient(project_id="my-proj", region="europe-west1")
            mock_genai.Client.assert_called_once_with(
                vertexai=True,
                project="my-proj",
                location="europe-west1",
            )

    @pytest.mark.asyncio
    async def test_extract_from_image(self):
        """extract_from_image sends image to Gemini and returns text."""
        with patch("agent_harness.llm.gemini_client.genai") as mock_genai:
            mock_response = MagicMock()
            mock_response.text = '{"page_text": "hello", "fields": {}}'
            mock_aio = AsyncMock(return_value=mock_response)
            mock_genai.Client.return_value.aio.models.generate_content = mock_aio

            client = GeminiClient(project_id="test")
            result = await client.extract_from_image(
                image_bytes=b"fake-png",
                prompt="Extract text",
            )
            assert result == '{"page_text": "hello", "fields": {}}'
            mock_aio.assert_called_once()


class TestVisionExtractInput:
    """Tests for VisionExtractInput dataclass."""

    def test_defaults(self):
        inp = VisionExtractInput(
            operativo_id="op-1",
            domain="dce",
            pdf_path="/tmp/test.pdf",
            pdf_filename="test.pdf",
        )
        assert inp.max_pages == 20

    def test_custom_max_pages(self):
        inp = VisionExtractInput(
            operativo_id="op-1",
            domain="dce",
            pdf_path="/tmp/test.pdf",
            pdf_filename="test.pdf",
            max_pages=5,
        )
        assert inp.max_pages == 5


class TestVisionExtractOutput:
    """Tests for VisionExtractOutput dataclass."""

    def test_source_default(self):
        out = VisionExtractOutput(
            operativo_id="op-1",
            pages_extracted=3,
            full_text="text",
            structured_fields="{}",
        )
        assert out.source == "gemini_vision"


class TestGeminiVisionExtract:
    """Tests for the gemini_vision_extract activity."""

    @pytest.mark.asyncio
    async def test_file_not_found(self):
        """Returns error output when PDF not found."""
        inp = VisionExtractInput(
            operativo_id="op-1",
            domain="dce",
            pdf_path="/nonexistent/file.pdf",
            pdf_filename="file.pdf",
        )
        # Activity uses activity.logger, mock it
        with patch("agent_harness.activities.vision_extract.activity"):
            result = await gemini_vision_extract(inp)
        assert result.pages_extracted == 0
        assert "File not found" in result.structured_fields

    @pytest.mark.asyncio
    async def test_single_page_extraction(self, tmp_path):
        """Extracts text from a single-page PDF."""
        pdf_path = str(tmp_path / "test.pdf")

        # Create a minimal valid PDF
        pdf_bytes = (
            b"%PDF-1.0\n1 0 obj<</Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</MediaBox[0 0 612 792]>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f \n"
            b"0000000009 00000 n \n0000000058 00000 n \n"
            b"0000000115 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n174\n%%EOF"
        )
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        gemini_response = json.dumps({
            "page_text": "Document Compliance Engine\nProduct: Toy Bear",
            "fields": {
                "product_description": "Toy Bear",
                "brand_name": "TestBrand",
            },
        })

        inp = VisionExtractInput(
            operativo_id="op-1",
            domain="dce",
            pdf_path=pdf_path,
            pdf_filename="test.pdf",
        )

        with patch(
            "agent_harness.llm.gemini_client.GeminiClient", autospec=False,
        ) as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.extract_from_image = AsyncMock(return_value=gemini_response)
            with patch("agent_harness.activities.vision_extract.activity"):
                result = await gemini_vision_extract(inp)

        assert result.pages_extracted == 1
        assert result.source == "gemini_vision"
        assert "Toy Bear" in result.full_text
        fields = json.loads(result.structured_fields)
        assert fields["product_description"] == "Toy Bear"
        assert fields["brand_name"] == "TestBrand"

    @pytest.mark.asyncio
    async def test_gemini_failure_graceful(self, tmp_path):
        """Handles Gemini API failure gracefully per page."""
        pdf_path = str(tmp_path / "test.pdf")
        pdf_bytes = (
            b"%PDF-1.0\n1 0 obj<</Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</MediaBox[0 0 612 792]>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f \n"
            b"0000000009 00000 n \n0000000058 00000 n \n"
            b"0000000115 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n174\n%%EOF"
        )
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        inp = VisionExtractInput(
            operativo_id="op-1",
            domain="dce",
            pdf_path=pdf_path,
            pdf_filename="test.pdf",
        )

        with patch(
            "agent_harness.llm.gemini_client.GeminiClient", autospec=False,
        ) as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.extract_from_image = AsyncMock(
                side_effect=Exception("Vertex AI unavailable")
            )
            with patch(
                "agent_harness.activities.vision_extract.activity"
            ) as mock_activity:
                mock_activity.logger = MagicMock()
                result = await gemini_vision_extract(inp)

        assert result.pages_extracted == 1
        assert "extraction failed" in result.full_text

    @pytest.mark.asyncio
    async def test_markdown_json_parsing(self, tmp_path):
        """Handles Gemini responses wrapped in markdown code fences."""
        pdf_path = str(tmp_path / "test.pdf")
        pdf_bytes = (
            b"%PDF-1.0\n1 0 obj<</Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</MediaBox[0 0 612 792]>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f \n"
            b"0000000009 00000 n \n0000000058 00000 n \n"
            b"0000000115 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n174\n%%EOF"
        )
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        # Gemini sometimes wraps JSON in markdown fences
        gemini_response = (
            '```json\n{"page_text": "DCE Document", "fields": {"brand_name": "Acme"}}\n```'
        )

        inp = VisionExtractInput(
            operativo_id="op-1",
            domain="dce",
            pdf_path=pdf_path,
            pdf_filename="test.pdf",
        )

        with patch(
            "agent_harness.llm.gemini_client.GeminiClient", autospec=False,
        ) as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.extract_from_image = AsyncMock(return_value=gemini_response)
            with patch("agent_harness.activities.vision_extract.activity"):
                result = await gemini_vision_extract(inp)

        assert result.pages_extracted == 1
        fields = json.loads(result.structured_fields)
        assert fields["brand_name"] == "Acme"


class TestVisionExtractionPrompt:
    """Tests for the extraction prompt."""

    def test_prompt_mentions_cpc_fields(self):
        assert "Product Description" in VISION_EXTRACTION_PROMPT
        assert "Brand Name" in VISION_EXTRACTION_PROMPT
        assert "Testing Laboratory" in VISION_EXTRACTION_PROMPT
        assert "ASTM F963" in VISION_EXTRACTION_PROMPT

    def test_prompt_requests_json(self):
        assert "JSON" in VISION_EXTRACTION_PROMPT
        assert "page_text" in VISION_EXTRACTION_PROMPT
        assert "fields" in VISION_EXTRACTION_PROMPT
