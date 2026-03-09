"""Gemini 3 Flash vision-based PDF extraction activity.

Renders PDF pages to images via pypdfium2, sends each page to Gemini 3 Flash
for visual text extraction, and aggregates results.
"""

import asyncio
import io
import json
import os
import re
from dataclasses import dataclass

from temporalio import activity


@dataclass(frozen=True)
class VisionExtractInput:
    """Input for the Gemini vision extraction activity."""

    operativo_id: str
    domain: str
    pdf_path: str
    pdf_filename: str
    max_pages: int = 20


@dataclass(frozen=True)
class VisionExtractOutput:
    """Output from the Gemini vision extraction activity."""

    operativo_id: str
    pages_extracted: int
    full_text: str
    structured_fields: str  # JSON string of extracted DCE fields
    source: str = "gemini_vision"


VISION_EXTRACTION_PROMPT = """You are analyzing a page from a Document Compliance Engine (DCE) document.

Extract ALL text visible on this page exactly as written. Then identify and structure the following DCE fields if present:

- Product Description / Identification
- Brand Name
- ASIN (if Amazon DCE)
- Importer / Domestic Manufacturer
- Place of Manufacture / Country of Origin
- Date(s) of Manufacture
- Testing Laboratory name and address
- Test Date(s)
- Test Report Number(s)
- Contact information (name, email, phone)
- Applicable regulations and standards (e.g., 16 CFR 1234, ASTM F963)
- Certification date

Respond with a JSON object:
{
    "page_text": "full verbatim text from the page",
    "fields": {
        "product_description": "...",
        "brand_name": "...",
        ...only include fields actually found on this page...
    }
}
"""

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.DOTALL)


@activity.defn
async def gemini_vision_extract(input: VisionExtractInput) -> VisionExtractOutput:
    """Extract text and DCE fields from PDF pages using Gemini 3 Flash vision.

    1. Opens PDF with pypdfium2
    2. Renders each page at 200 DPI to PNG
    3. Sends page images to Gemini 3 Flash via Vertex AI
    4. Aggregates per-page results
    """
    import pypdfium2 as pdfium

    from agent_harness.llm.gemini_client import GeminiClient

    if not os.path.isfile(input.pdf_path):
        return VisionExtractOutput(
            operativo_id=input.operativo_id,
            pages_extracted=0,
            full_text="",
            structured_fields=json.dumps({"error": f"File not found: {input.pdf_path}"}),
        )

    client = GeminiClient()

    # Open PDF and render pages
    pdf = pdfium.PdfDocument(input.pdf_path)
    try:
        total_pages = len(pdf)
        pages_to_process = min(total_pages, input.max_pages)

        all_text_parts: list[str] = []
        all_fields: dict[str, str] = {}
        batch_size = 4

        async def _extract_page(page_idx: int) -> tuple[int, str, dict[str, str]]:
            page = pdf[page_idx]
            # Render at 200 DPI (scale factor = 200/72 ~ 2.77)
            bitmap = page.render(scale=200 / 72)
            pil_image = bitmap.to_pil()

            # Convert to PNG bytes
            buffer = io.BytesIO()
            pil_image.save(buffer, format="PNG")
            image_bytes = buffer.getvalue()

            response_text = await client.extract_from_image(
                image_bytes=image_bytes,
                prompt=VISION_EXTRACTION_PROMPT,
            )

            # Parse JSON response — use regex to extract from markdown fences
            json_text = response_text
            match = _JSON_FENCE_RE.search(json_text)
            if match:
                json_text = match.group(1)

            page_data = json.loads(json_text.strip())
            page_text = page_data.get("page_text", "")
            page_fields = page_data.get("fields", {})
            if not isinstance(page_fields, dict):
                page_fields = {}
            return page_idx, page_text, page_fields

        for batch_start in range(0, pages_to_process, batch_size):
            batch_indices = range(batch_start, min(batch_start + batch_size, pages_to_process))
            batch_results = await asyncio.gather(
                *[_extract_page(idx) for idx in batch_indices],
                return_exceptions=True,
            )
            for idx, result in zip(batch_indices, batch_results, strict=False):
                if isinstance(result, Exception):
                    activity.logger.warning(
                        "Gemini vision failed for page %d of %s: %s",
                        idx + 1,
                        input.pdf_filename,
                        result,
                    )
                    all_text_parts.append(
                        f"--- Page {idx + 1} ---\n[extraction failed: {result}]"
                    )
                    continue

                page_idx, page_text, page_fields = result
                all_text_parts.append(f"--- Page {page_idx + 1} ---\n{page_text}")
                # Merge fields (later pages don't overwrite earlier non-empty values)
                for key, value in page_fields.items():
                    if key not in all_fields or not all_fields[key]:
                        all_fields[key] = value
    finally:
        pdf.close()

    return VisionExtractOutput(
        operativo_id=input.operativo_id,
        pages_extracted=pages_to_process,
        full_text="\n\n".join(all_text_parts),
        structured_fields=json.dumps(all_fields),
        source="gemini_vision",
    )
