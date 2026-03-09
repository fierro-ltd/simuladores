"""End-to-end integration test: PDF extraction + DCE field parsing on real data.

Two test classes:
1. TestE2ECpcLocal — Uses local pdfplumber extraction (no external deps).
2. TestE2ECpcRobot — Uses DCE Backend Temporal activities (requires running DCE Backend).

Requires real DCE PDF files in the DCE_DATA_DIR directory.
Skipped automatically when sample data is not available.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from agent_harness.activities.factory import (
    _handle_extract_pdf_text,
    _handle_extract_pdf_text_local,
    _handle_extract_cpc_data,
    _extract_cpc_fields,
)

# ---------------------------------------------------------------------------
# Skip conditions
# ---------------------------------------------------------------------------

CPC_DATA_DIR = Path(os.environ.get("CPC_DATA_DIR", "/Users/metallo/Downloads/dce-data"))

_has_cpc_data = CPC_DATA_DIR.is_dir() and any(CPC_DATA_DIR.glob("*.pdf"))

skip_no_data = pytest.mark.skipif(
    not _has_cpc_data,
    reason=f"DCE sample data not available at {CPC_DATA_DIR}",
)


def _get_smallest_pdf() -> Path | None:
    """Return the smallest PDF in the DCE data directory, or None."""
    if not _has_cpc_data:
        return None
    pdfs = sorted(CPC_DATA_DIR.glob("*.pdf"), key=lambda p: p.stat().st_size)
    return pdfs[0] if pdfs else None


# ---------------------------------------------------------------------------
# Local extraction tests (pdfplumber, no DCE Backend needed)
# ---------------------------------------------------------------------------


@skip_no_data
class TestE2ECpcLocal:
    """E2E tests using local pdfplumber extraction."""

    @pytest.mark.asyncio
    async def test_extract_text_from_real_pdf(self) -> None:
        """Verify pdfplumber can extract text from a real DCE PDF."""
        pdf_path = _get_smallest_pdf()
        assert pdf_path is not None

        result = await _handle_extract_pdf_text_local({"pdf_path": str(pdf_path)})
        data = json.loads(result)

        assert "error" not in data, f"Extraction failed: {data.get('error')}"
        assert data["total_pages"] >= 1
        assert data["pages_extracted"] >= 1
        assert data["char_count"] > 100
        assert data["source"] == "local_pdfplumber"

    @pytest.mark.asyncio
    async def test_extract_cpc_fields_from_real_pdf(self) -> None:
        """Full local pipeline: PDF -> text -> DCE field extraction."""
        pdf_path = _get_smallest_pdf()
        assert pdf_path is not None

        text_result = await _handle_extract_pdf_text_local({"pdf_path": str(pdf_path)})
        text_data = json.loads(text_result)
        assert "error" not in text_data

        cpc_result = await _handle_extract_cpc_data({"pdf_text": text_data["text"]})
        cpc_data = json.loads(cpc_result)
        assert cpc_data["fields_extracted"] >= 1

    @pytest.mark.asyncio
    async def test_all_pdfs_extract_without_errors(self) -> None:
        """Every PDF in the sample data directory extracts without errors."""
        pdfs = list(CPC_DATA_DIR.glob("*.pdf"))
        assert len(pdfs) >= 1

        for pdf_path in pdfs:
            result = await _handle_extract_pdf_text_local({"pdf_path": str(pdf_path)})
            data = json.loads(result)
            assert "error" not in data, (
                f"Extraction failed for {pdf_path.name}: {data.get('error')}"
            )
            assert data["pages_extracted"] >= 1

    @pytest.mark.asyncio
    async def test_pipeline_consistency(self) -> None:
        """Running the pipeline twice yields identical results."""
        pdf_path = _get_smallest_pdf()
        assert pdf_path is not None

        result1 = await _handle_extract_pdf_text_local({"pdf_path": str(pdf_path)})
        result2 = await _handle_extract_pdf_text_local({"pdf_path": str(pdf_path)})
        assert result1 == result2

        data = json.loads(result1)
        cpc1 = await _handle_extract_cpc_data({"pdf_text": data["text"]})
        cpc2 = await _handle_extract_cpc_data({"pdf_text": data["text"]})
        assert cpc1 == cpc2


# ---------------------------------------------------------------------------
# DCE Backend integration tests (requires running DCE Backend on localhost:8000)
# ---------------------------------------------------------------------------

_dce_backend_url = os.environ.get("DCE_BACKEND_URL", "http://localhost:8000")


def _dce_backend_available() -> bool:
    """Check if DCE Backend API is reachable."""
    try:
        import httpx
        resp = httpx.get(f"{_dce_backend_url}/health", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


skip_no_robot = pytest.mark.skipif(
    not _dce_backend_available(),
    reason=f"DCE Backend not available at {_dce_backend_url}",
)


@skip_no_data
@skip_no_robot
class TestE2ECpcRobot:
    """E2E tests dispatching to DCE Backend's Temporal activities."""

    @pytest.mark.asyncio
    async def test_extract_via_dce_backend(self) -> None:
        """Upload PDF to DCE Backend, get full extraction result."""
        pdf_path = _get_smallest_pdf()
        assert pdf_path is not None

        result = await _handle_extract_pdf_text({"pdf_path": str(pdf_path)})
        data = json.loads(result)

        assert "error" not in data, f"DCE Backend failed: {data.get('error')}"
        assert data.get("status") == "completed"
        assert data.get("job_id") is not None

        # DCE Backend returns structured extraction
        extraction = data.get("extraction", {})
        assert extraction, "DCE Backend should return extraction data"

    @pytest.mark.asyncio
    async def test_dce_backend_extraction_has_citations(self) -> None:
        """DCE Backend extraction includes parsed citations."""
        pdf_path = _get_smallest_pdf()
        assert pdf_path is not None

        result = await _handle_extract_pdf_text({"pdf_path": str(pdf_path)})
        data = json.loads(result)
        assert "error" not in data

        extraction = data.get("extraction", {})
        citations = extraction.get("Citations", extraction.get("citations", []))
        assert len(citations) > 0, "Real DCE PDF should have at least one citation"

    @pytest.mark.asyncio
    async def test_dce_backend_merged_assessment(self) -> None:
        """DCE Backend produces a merged assessment."""
        pdf_path = _get_smallest_pdf()
        assert pdf_path is not None

        result = await _handle_extract_pdf_text({"pdf_path": str(pdf_path)})
        data = json.loads(result)
        assert "error" not in data

        assessment = data.get("merged_assessment")
        assert assessment is not None, "DCE Backend should produce a merged assessment"
        assert "overall_verdict" in assessment
