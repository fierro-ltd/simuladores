"""Gemini client for Vertex AI vision extraction.

Uses the google-genai SDK with Vertex AI ADC authentication.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from google import genai
from google.genai.types import Part


@dataclass(frozen=True)
class GeminiVisionResult:
    """Result from a Gemini vision extraction call."""

    text: str
    page_number: int
    model: str = ""


class GeminiClient:
    """Thin wrapper around google-genai for Vertex AI Gemini calls.

    Uses Application Default Credentials (ADC) for authentication,
    consistent with the existing AnthropicClient pattern.
    """

    def __init__(
        self,
        project_id: str | None = None,
        region: str = "us-central1",
        model: str = "gemini-2.0-flash",
    ) -> None:
        self._project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not self._project_id:
            raise ValueError(
                "GOOGLE_CLOUD_PROJECT environment variable is required but not set."
            )
        self._region = region
        self._model = model
        self._client = genai.Client(
            vertexai=True,
            project=self._project_id,
            location=self._region,
        )

    async def extract_from_image(
        self,
        image_bytes: bytes,
        prompt: str,
        mime_type: str = "image/png",
    ) -> str:
        """Send an image to Gemini and extract text/structured content.

        Args:
            image_bytes: Raw image bytes (PNG).
            prompt: Extraction prompt.
            mime_type: Image MIME type.

        Returns:
            Extracted text from Gemini's response.
        """
        image_part = Part.from_bytes(data=image_bytes, mime_type=mime_type)

        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=[prompt, image_part],
        )

        return response.text or ""
