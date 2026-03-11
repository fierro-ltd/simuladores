"""Activity factory helpers: client creation, tool handler construction, domain memory loading."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from agent_harness.domains.dce.tools import discover_api, get_operation_schema
from agent_harness.domains.idp.tools import (
    discover_api as idp_discover_api,
    get_operation_schema as idp_get_operation_schema,
)
from agent_harness.llm.client import AnthropicClient
from agent_harness.llm.tool_handler import ToolHandler
from agent_harness.memory.domain_store import DomainStore
from agent_harness.memory.session_store import SessionStore
from agent_harness.prompt.injection_guard import scan_content, scan_document
from agent_harness.storage.backend import StorageBackend
from agent_harness.storage.local import LocalStorageBackend


# ---------------------------------------------------------------------------
# Cache monitor singleton for worker-process-wide usage tracking
# ---------------------------------------------------------------------------

_cache_monitor = None


def get_cache_monitor():
    """Return process-wide CacheMonitor singleton (lazy-initialized)."""
    global _cache_monitor  # noqa: PLW0603
    if _cache_monitor is None:
        from agent_harness.observability.cache_monitor import CacheMonitor
        _cache_monitor = CacheMonitor()
    return _cache_monitor


def get_anthropic_client() -> AnthropicClient:
    """Create AnthropicClient from GOOGLE_CLOUD_PROJECT env var.

    Uses Vertex AI via Application Default Credentials.

    Raises:
        ValueError: If GOOGLE_CLOUD_PROJECT is not set.
    """
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        raise ValueError(
            "GOOGLE_CLOUD_PROJECT environment variable is required but not set."
        )
    region = os.environ.get("VERTEX_REGION", "europe-west1")
    return AnthropicClient(project_id=project_id, region=region)


# ---------------------------------------------------------------------------
# DCE tool handler functions
# ---------------------------------------------------------------------------


async def _handle_discover_api(params: dict[str, Any]) -> str:
    """Wrap discover_api from DCE tools manifest."""
    category = params.get("category")
    return discover_api(category=category)


async def _handle_execute_api(params: dict[str, Any]) -> str:
    """Validate operation exists via get_operation_schema, return confirmation."""
    operation = params.get("operation", "")
    op_params = params.get("params", {})
    schema = get_operation_schema(operation)
    if schema is None:
        return json.dumps({"error": f"Unknown operation: {operation}"})
    return json.dumps({
        "status": "executed",
        "operation": operation,
        "params": op_params,
        "schema": schema,
    })


async def _handle_extract_pdf_text(params: dict[str, Any]) -> str:
    """Extract text from a PDF by dispatching to the DCE Backend via its REST API.

    Uploads the PDF to the DCE Backend's /jobs/upload endpoint, polls until the
    Temporal workflow completes, then returns the extraction result.

    Falls back to local pdfplumber extraction if the DCE Backend is unavailable.

    Params:
        pdf_path: Absolute path to the PDF file.

    Returns:
        JSON string with extracted text, page count, and character count.
        On error, returns JSON with an "error" key.
    """
    import asyncio
    import httpx

    pdf_path = params.get("pdf_path", "")
    if not pdf_path:
        return json.dumps({"error": "pdf_path is required"})
    if not os.path.isfile(pdf_path):
        return json.dumps({"error": f"File not found: {pdf_path}"})

    dce_backend_url = os.environ.get("DCE_BACKEND_URL", "http://localhost:8000")

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            # Upload PDF to DCE Backend
            with open(pdf_path, "rb") as f:
                resp = await client.post(
                    f"{dce_backend_url}/jobs/upload",
                    files={"file": (os.path.basename(pdf_path), f, "application/pdf")},
                )
            resp.raise_for_status()
            job = resp.json()
            job_id = job["job_id"]
            operativo_id = params.get("operativo_id")

            # Persist DCE API job id so diagnostics can correlate workflow <> API run.
            if operativo_id:
                try:
                    root = os.environ.get("STORAGE_ROOT", "/tmp/agent-harness")
                    backend = LocalStorageBackend(root=root)
                    key = f"sessions/{operativo_id}/cpc_job_id.txt"
                    await backend.write(key, job_id.encode("utf-8"))
                except Exception:
                    # Diagnostics helper should never break extraction flow.
                    pass

            # Poll until job completes (max 5 minutes).
            # Check extraction endpoint from the first poll — extraction may be
            # ready while downstream activities are still running.
            status_data = {}
            extraction = {}
            elapsed = 0.0
            max_wait_s = 300.0
            while elapsed < max_wait_s:
                if not extraction:
                    try:
                        ext_resp = await client.get(f"{dce_backend_url}/jobs/{job_id}/extraction")
                        ext_resp.raise_for_status()
                        ext_data = ext_resp.json()
                        extraction = ext_data.get("extraction", {})
                    except Exception:
                        pass

                status_resp = await client.get(f"{dce_backend_url}/jobs/{job_id}")
                status_resp.raise_for_status()
                status_data = status_resp.json()

                if status_data.get("status") != "running":
                    break

                sleep_s = 2.0 if elapsed < 20.0 else 5.0
                await asyncio.sleep(sleep_s)
                elapsed += sleep_s

            # Final extraction fetch if not already obtained
            if not extraction:
                try:
                    ext_resp = await client.get(f"{dce_backend_url}/jobs/{job_id}/extraction")
                    ext_resp.raise_for_status()
                    ext_data = ext_resp.json()
                    extraction = ext_data.get("extraction", {})
                except Exception:
                    pass

            # If no extraction at all and job errored, return error
            if status_data.get("error") and not extraction:
                return json.dumps({"error": f"DCE Backend failed: {status_data['error']}"})

            result = {
                "job_id": job_id,
                "status": "completed" if not status_data.get("error") else "partial",
                "extraction": extraction,
                "item_id": status_data.get("item_id"),
                "isam_product": status_data.get("isam_product"),
                "validation": status_data.get("validation"),
                "merged_assessment": status_data.get("merged_assessment"),
            }
            if status_data.get("error"):
                result["error"] = status_data["error"]
            return json.dumps(result)

    except httpx.ConnectError:
        # DCE Backend not available — fall back to local pdfplumber
        return await _handle_extract_pdf_text_local(params)
    except Exception as exc:
        return json.dumps({"error": f"DCE Backend dispatch failed: {exc}"})


async def _handle_extract_pdf_text_local(params: dict[str, Any]) -> str:
    """Local fallback: extract text using pdfplumber when DCE Backend is unavailable."""
    import pdfplumber

    pdf_path = params.get("pdf_path", "")
    max_pages = params.get("max_pages", 50)

    try:
        pages_text: list[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            for page in pdf.pages[:max_pages]:
                text = page.extract_text()
                if text:
                    pages_text.append(text)

        full_text = "\n\n".join(pages_text)
        return json.dumps({
            "text": full_text,
            "pages_extracted": len(pages_text),
            "total_pages": total_pages,
            "char_count": len(full_text),
            "source": "local_pdfplumber",
        })
    except Exception as exc:
        return json.dumps({"error": f"PDF extraction failed: {exc}"})


async def _handle_scan_content(params: dict[str, Any]) -> str:
    """Wrap injection_guard.scan_content, with optional metadata scanning."""
    text = params.get("text", "")
    metadata = params.get("metadata")
    if metadata:
        result = scan_document(text, metadata)
    else:
        result = scan_content(text)
    return json.dumps({
        "risk": str(result.risk),
        "matched_pattern": result.matched_pattern,
        "raw_match": result.raw_match,
    })


def _extract_cpc_fields(text: str) -> dict[str, Any]:
    """Parse structured DCE fields from extracted PDF text using heuristic regexes.

    Handles multiple DCE formats (Amazon-style, manufacturer-style, etc.).
    Labels may have values on the same line or the next line.
    Returns a dict of extracted fields. Fields not found are omitted.
    """
    fields: dict[str, Any] = {}

    # Helper: match "Label: value" or "Label\nvalue" (value on next line)
    def _find(pattern: str, flags: int = re.IGNORECASE) -> str | None:
        m = re.search(pattern, text, flags)
        return m.group(1).strip() if m else None

    # Product Identification / Description / SKU
    val = (
        _find(r"Product\s*(?:Description|Identification)\s*[:/]?\s*\n?\s*(.+)")
        or _find(r"Product\s*Description\s*/?\s*SKU\s+(.+)")
    )
    if val:
        fields["product_description"] = val

    # Brand Name
    val = _find(r"Brand\s*Name\s*[:/]?\s*\n?\s*(.+)")
    if val:
        fields["brand_name"] = val

    # ASIN (Amazon-style CPCs)
    val = _find(r"ASIN\s*(?:No\.?)?\s*:?\s*([A-Z0-9]{10})")
    if val:
        fields["asin"] = val

    # Seller ID (Amazon-style CPCs)
    val = _find(r"Seller\s*ID\s*[:/]?\s*([A-Z0-9]+)")
    if val:
        fields["seller_id"] = val

    # Importer — multiple label variants
    val = (
        _find(r"Importer\s*[:/]?\s*\n\s*(.+)")
        or _find(r"(?:US\s*)?IMPORTER\s*/?\s*(?:DOMESTIC\s*MANUFACTURER)?\s*:?\s*\n?\s*(.+)")
        or _find(r"Imported\s*by\s*[:/]?\s*\n?\s*(.+)")
    )
    if val:
        fields["importer"] = val

    # Place / Country of Manufacture — "Product Made In:" or "Place of Manufacture:"
    val = (
        _find(r"Product\s*Made\s*In\s*[:/]?\s*\n\s*(.+)")
        or _find(r"Place\s*of\s*Manufacture\s*[:/]?\s*\n?\s*(.+)")
        or _find(r"(?:Country|Made)\s*(?:of|in)\s*(?:Origin|Manufacture)\s*[:/]?\s*\n?\s*(.+)")
    )
    if val:
        val = re.split(r"\s+(?:Start|Date)\s", val, flags=re.IGNORECASE)[0].strip()
        if val:
            fields["place_of_manufacture"] = val

    # Manufacture date — "Date of Manufacture:" or start/end range
    val = _find(r"Date\s*of\s*Manufacture\s*[:/]?\s*\n?\s*([\d./\-]+(?:\s*[-–]\s*[\d./\-]+)?)")
    if val:
        fields["manufacture_date"] = val
    else:
        m_start = _find(r"Start\s*Date\s*[:/]?\s*([\d/.\-]+)")
        m_end = _find(r"End\s*Date\s*[:/]?\s*([\d/.\-]+)")
        if m_start:
            fields["manufacture_start_date"] = m_start
        if m_end:
            fields["manufacture_end_date"] = m_end

    # Testing lab — "Tested By:", "Testing Laboratory:", "Lab #1"
    val = (
        _find(r"Tested\s*By\s*[:/]?\s*\n\s*(.+)")
        or _find(r"Testing\s*Lab(?:oratory)?\s*[:/]?\s*\n?\s*(.+)")
        or _find(r"Lab\s*#?\s*1\s*[-–]?\s*(?:Name\s*&?\s*Address)\s*[:/]?\s*\n?\s*(.+)")
    )
    if val:
        fields["testing_lab"] = val

    # Test date(s)
    val = (
        _find(r"Test\s*[Dd]ate\s*(?:\(s\))?\s*[:/]?\s*\n?\s*([\d./\-]+(?:\s*(?:to|[-–])\s*[\d./\-]+)?)")
    )
    if val:
        fields["test_date"] = val

    # Test report number — "Test #:", "Test No.", "Report No."
    val = _find(r"Test\s*(?:#|No\.?)\s*:?\s*\n?\s*([A-Z0-9]{8,})")
    if val:
        fields["test_report_number"] = val

    # Contact info
    val = _find(r"(?:Contact|Certifier)\s*[:/]?\s*\n?\s*([A-Z][a-zA-Z\s]+(?:\([^)]+\))?)")
    if val:
        fields["contact"] = val

    # Email
    val = _find(r"(?:Email|E-mail)\s*[:/]?\s*\n?\s*([\w.\-+]+@[\w.\-]+)")
    if val:
        fields["email"] = val

    # Applicable regulations — match "16CFR1252", "ASTMF963-23", "compliance Sec101", etc.
    regulations: list[str] = []
    for reg_match in re.finditer(
        r"((?:16\s*CFR\s*\d+|ASTM\s*F?\d+(?:-\d+)?|compliance\s*(?:Sec(?:tion)?\s*\d+|Lead)|"
        r"SOR-\d+-\d+|40\s*CFR\s*(?:Part\s*)?\d+|FDA\s*(?:CFR)?\s*\d+))",
        text,
        re.IGNORECASE,
    ):
        regulations.append(reg_match.group(1).strip())
    if regulations:
        fields["regulations"] = list(dict.fromkeys(regulations))

    return fields


def _extract_product_profile(
    cpc_data: dict[str, Any] | None = None,
    text: str = "",
) -> dict[str, Any]:
    """Derive deterministic product profile from DCE data/text for citation completeness.

    Parses age range, product category, material flags, and children's product status
    with robust heuristics and safe defaults.

    Returns:
        Dict with: age_min_months, age_max_months, is_childrens_product, product_category,
        is_toy, is_child_care_article, has_painted_surface, has_plasticized_material,
        has_battery, confidence, notes.
    """
    data: dict[str, Any] = {}
    if cpc_data and isinstance(cpc_data, dict):
        data = dict(cpc_data)
    if text:
        data.update(_extract_cpc_fields(text))

    def _safe_int(val: Any) -> int | None:
        if val is None:
            return None
        if isinstance(val, int):
            return val if val >= 0 else None
        if isinstance(val, (float, str)):
            try:
                n = int(float(str(val).strip()))
                return n if n >= 0 else None
            except (ValueError, TypeError):
                return None
        return None

    def _parse_age_months(s: str) -> tuple[int | None, int | None]:
        """Parse age range from text; returns (min, max) in months."""
        s = str(s).lower()
        min_m, max_m = None, None
        # "0-3 months", "0-36 months", "3+", "36+"
        m = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*(?:months?|mo\.?)?", s)
        if m:
            min_m, max_m = _safe_int(m.group(1)), _safe_int(m.group(2))
        else:
            m = re.search(r"(?:under|below|≤|<=)\s*(\d+)\s*(?:months?|mo\.?)?", s)
            if m:
                max_m = _safe_int(m.group(1))
                min_m = 0
            else:
                m = re.search(r"(\d+)\s*\+\s*(?:months?|mo\.?)?", s)
                if m:
                    min_m = _safe_int(m.group(1))
                    max_m = None
                else:
                    m = re.search(r"(\d+)\s*(?:months?|mo\.?)\s*(?:and\s*)?(?:under|below)", s)
                    if m:
                        max_m = _safe_int(m.group(1))
                        min_m = 0
        return (min_m, max_m)

    # Resolve text to search for age/category
    search_text = (
        str(data.get("product_description", ""))
        + " "
        + str(data.get("product_name", ""))
        + " "
        + str(data.get("age_grade", ""))
        + " "
        + str(data.get("age_range", ""))
        + " "
        + text
    ).lower()

    age_min = _safe_int(data.get("age_min_months")) or _safe_int(data.get("age_min"))
    age_max = _safe_int(data.get("age_max_months")) or _safe_int(data.get("age_max"))
    if age_min is None and age_max is None:
        parsed_min, parsed_max = _parse_age_months(search_text)
        if parsed_min is not None or parsed_max is not None:
            age_min = parsed_min or 0
            age_max = parsed_max

    # is_childrens_product: true if age_max <= 36 months (compliance definition)
    is_childrens = False
    if age_max is not None and age_max <= 36:
        is_childrens = True
    elif age_max is None and age_min is not None and age_min <= 36:
        is_childrens = True

    # product_category: infer from description
    category = str(data.get("product_category", "")).strip() or ""
    desc = search_text
    if not category:
        if re.search(r"\bdresser\b", desc):
            category = "dresser"
        elif re.search(r"\bcrib\b", desc):
            category = "crib"
        elif re.search(r"\bbassinet\b", desc):
            category = "bassinet"
        elif re.search(r"\bchanging\s*table\b", desc):
            category = "changing_table"
        elif re.search(r"\bhigh\s*chair\b", desc):
            category = "high_chair"
        elif re.search(r"\bchild\s*care\s*article\b", desc):
            category = "child_care_article"
        elif re.search(r"\btoy\b", desc):
            category = "toy"
        elif re.search(r"\bplush\b|\bstuffed\b", desc):
            category = "toy"
        else:
            category = ""

    # is_toy: explicit or inferred from category; dresser/crib etc. are NOT toys
    is_toy = bool(data.get("is_toy"))
    if not is_toy and category:
        is_toy = category == "toy"
    if not is_toy and not category:
        is_toy = bool(re.search(r"\btoy\b", desc))

    # is_child_care_article: dresser, crib, bassinet, etc. (16 CFR 1261)
    child_care_categories = {"dresser", "crib", "bassinet", "changing_table", "high_chair", "child_care_article"}
    is_child_care = category.lower() in child_care_categories if category else False
    if not is_child_care and re.search(r"\b(?:dresser|crib|bassinet|changing\s*table|high\s*chair)\b", desc):
        is_child_care = True

    # Override: dresser/crib context -> is_toy = False
    if is_child_care:
        is_toy = False

    # Material flags
    has_painted = bool(
        data.get("has_painted_surface")
        or re.search(r"\bpainted\s*surface\b|\bpaint\b", desc)
    )
    has_plasticized = bool(
        data.get("has_plasticized_material")
        or re.search(r"\bplastic(?:ized|e)?\b|\bvinyl\b|\bphthalate", desc)
    )
    has_battery = bool(
        data.get("has_battery")
        or re.search(r"\bbatter(?:y|ies)\b|\belectronic\b", desc)
    )

    # Confidence: higher when we have explicit age or category
    confidence = 0.5
    if age_min is not None or age_max is not None:
        confidence += 0.2
    if category:
        confidence += 0.2
    if is_childrens or is_toy or is_child_care:
        confidence += 0.1
    confidence = min(1.0, confidence)

    notes_parts: list[str] = []
    if not category and desc.strip():
        notes_parts.append("category inferred from description")
    if age_min is None and age_max is None and "month" in desc:
        notes_parts.append("age range not parsed")

    return {
        "age_min_months": age_min,
        "age_max_months": age_max,
        "is_childrens_product": is_childrens,
        "product_category": category or "unknown",
        "is_toy": is_toy,
        "is_child_care_article": is_child_care,
        "has_painted_surface": has_painted,
        "has_plasticized_material": has_plasticized,
        "has_battery": has_battery,
        "confidence": round(confidence, 2),
        "notes": "; ".join(notes_parts) if notes_parts else "",
    }


async def _handle_extract_product_profile(params: dict[str, Any]) -> str:
    """Extract deterministic product profile from DCE data/text for citation completeness.

    Params:
        cpc_data: Optional dict from extract_cpc_data or DCE Backend extraction.
        text: Optional raw text for fallback parsing.

    Returns:
        JSON string with product profile fields.
    """
    cpc_data = params.get("cpc_data")
    text = params.get("text", "")
    if not cpc_data and not text:
        return json.dumps({"error": "cpc_data or text is required"})
    if cpc_data is not None and not isinstance(cpc_data, dict):
        return json.dumps({"error": "cpc_data must be a dict"})
    profile = _extract_product_profile(cpc_data=cpc_data, text=text)
    return json.dumps(profile)


async def _handle_extract_cpc_data(params: dict[str, Any]) -> str:
    """Extract structured DCE fields from PDF text.

    If a DCE Backend extraction result is provided (from _handle_extract_pdf_text),
    returns it directly. Otherwise falls back to local heuristic regex parsing.

    Params:
        pdf_text: Raw text extracted from a DCE PDF document.
        extraction: Optional pre-computed extraction from DCE Backend.

    Returns:
        JSON string with extracted DCE fields and a fields_extracted count.
    """
    # If DCE Backend extraction is available, use it directly
    extraction = params.get("extraction")
    if extraction and isinstance(extraction, dict):
        return json.dumps(extraction)

    # Fall back to local heuristic parsing
    pdf_text = params.get("pdf_text", "")
    if not pdf_text:
        return json.dumps({"error": "pdf_text is required", "fields_extracted": 0})

    fields = _extract_cpc_fields(pdf_text)
    fields["fields_extracted"] = len(fields)
    return json.dumps(fields)


# Map of all DCE tool handlers
_CPC_TOOL_HANDLERS = {
    "discover_api": _handle_discover_api,
    "execute_api": _handle_execute_api,
    "extract_pdf_text": _handle_extract_pdf_text,
    "scan_content": _handle_scan_content,
    "extract_cpc_data": _handle_extract_cpc_data,
    "extract_product_profile": _handle_extract_product_profile,
}


# ---------------------------------------------------------------------------
# IDP Platform tool handler functions
# ---------------------------------------------------------------------------


def _get_idp_client() -> tuple[str, dict[str, str]]:
    """Return (base_url, headers) for IDP Platform API."""
    base_url = os.environ.get("IDP_PLATFORM_URL", "http://localhost:8100")
    token = os.environ.get("IDP_PLATFORM_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return base_url, headers


async def _handle_idp_discover_api(params: dict[str, Any]) -> str:
    """Wrap discover_api from IDP tools manifest."""
    category = params.get("category")
    return idp_discover_api(category=category)


async def _handle_idp_execute_api(params: dict[str, Any]) -> str:
    """Validate operation exists via IDP get_operation_schema, return confirmation."""
    operation = params.get("operation", "")
    op_params = params.get("params", {})
    schema = idp_get_operation_schema(operation)
    if schema is None:
        return json.dumps({"error": f"Unknown IDP operation: {operation}"})
    return json.dumps({
        "status": "executed",
        "operation": operation,
        "params": op_params,
        "schema": schema,
    })


async def _handle_idp_upload_document(params: dict[str, Any]) -> str:
    """Upload a document to IDP Platform via POST /api/jobs.

    Params:
        document_path: Absolute path to the document file.
        plugin_id: Plugin to process with.

    Returns:
        JSON string with job details or error.
    """
    import httpx

    document_path = params.get("document_path", "")
    plugin_id = params.get("plugin_id", "")
    if not document_path:
        return json.dumps({"error": "document_path is required"})
    if not os.path.isfile(document_path):
        return json.dumps({"error": f"File not found: {document_path}"})
    if not plugin_id:
        return json.dumps({"error": "plugin_id is required"})

    base_url, headers = _get_idp_client()
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            with open(document_path, "rb") as f:
                resp = await client.post(
                    f"{base_url}/api/jobs",
                    files={"file": (os.path.basename(document_path), f, "application/pdf")},
                    data={"plugin_id": plugin_id},
                    headers=headers,
                )
            resp.raise_for_status()
            return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": f"IDP upload failed: {exc}"})


async def _handle_idp_get_job_detail(params: dict[str, Any]) -> str:
    """GET /api/jobs/{job_id} — full job detail with stage results."""
    import httpx

    job_id = params.get("job_id", "")
    if not job_id:
        return json.dumps({"error": "job_id is required"})

    base_url, headers = _get_idp_client()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{base_url}/api/jobs/{job_id}", headers=headers)
            resp.raise_for_status()
            return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": f"IDP get_job_detail failed: {exc}"})


async def _handle_idp_get_job_status(params: dict[str, Any]) -> str:
    """GET /api/jobs/{job_id}/status — lightweight status poll."""
    import httpx

    job_id = params.get("job_id", "")
    if not job_id:
        return json.dumps({"error": "job_id is required"})

    base_url, headers = _get_idp_client()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{base_url}/api/jobs/{job_id}/status", headers=headers)
            resp.raise_for_status()
            return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": f"IDP get_job_status failed: {exc}"})


async def _handle_idp_list_jobs(params: dict[str, Any]) -> str:
    """GET /api/jobs with optional plugin_id and limit query params."""
    import httpx

    base_url, headers = _get_idp_client()
    query: dict[str, Any] = {}
    if params.get("plugin_id"):
        query["plugin_id"] = params["plugin_id"]
    if params.get("limit"):
        query["limit"] = params["limit"]

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{base_url}/api/jobs", params=query, headers=headers)
            resp.raise_for_status()
            return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": f"IDP list_jobs failed: {exc}"})


async def _handle_idp_patch_job_verdict(params: dict[str, Any]) -> str:
    """PATCH /api/jobs/{job_id} with verdict."""
    import httpx

    job_id = params.get("job_id", "")
    verdict = params.get("verdict", "")
    if not job_id:
        return json.dumps({"error": "job_id is required"})
    if not verdict:
        return json.dumps({"error": "verdict is required"})

    base_url, headers = _get_idp_client()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(
                f"{base_url}/api/jobs/{job_id}",
                json={"verdict": verdict},
                headers=headers,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": f"IDP patch_job_verdict failed: {exc}"})


async def _handle_idp_list_plugins(params: dict[str, Any]) -> str:
    """GET /api/plugins."""
    import httpx

    base_url, headers = _get_idp_client()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{base_url}/api/plugins", headers=headers)
            resp.raise_for_status()
            return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": f"IDP list_plugins failed: {exc}"})


async def _handle_idp_get_plugin(params: dict[str, Any]) -> str:
    """GET /api/plugins/{plugin_id}."""
    import httpx

    plugin_id = params.get("plugin_id", "")
    if not plugin_id:
        return json.dumps({"error": "plugin_id is required"})

    base_url, headers = _get_idp_client()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{base_url}/api/plugins/{plugin_id}", headers=headers)
            resp.raise_for_status()
            return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": f"IDP get_plugin failed: {exc}"})


async def _handle_idp_update_schema(params: dict[str, Any]) -> str:
    """PUT /api/plugins/{plugin_id}/schema with schema and change_description."""
    import httpx

    plugin_id = params.get("plugin_id", "")
    schema = params.get("schema")
    change_description = params.get("change_description", "")
    if not plugin_id:
        return json.dumps({"error": "plugin_id is required"})
    if schema is None:
        return json.dumps({"error": "schema is required"})

    base_url, headers = _get_idp_client()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.put(
                f"{base_url}/api/plugins/{plugin_id}/schema",
                json={"schema": schema, "change_description": change_description},
                headers=headers,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": f"IDP update_schema failed: {exc}"})


async def _handle_idp_calibrate_schema(params: dict[str, Any]) -> str:
    """POST /api/plugins/{plugin_id}/calibrate — multipart upload of sample documents."""
    import httpx

    plugin_id = params.get("plugin_id", "")
    document_paths = params.get("document_paths", [])
    if not plugin_id:
        return json.dumps({"error": "plugin_id is required"})
    if not document_paths:
        return json.dumps({"error": "document_paths is required"})

    # Validate all paths exist before uploading
    for path in document_paths:
        if not os.path.isfile(path):
            return json.dumps({"error": f"File not found: {path}"})

    base_url, headers = _get_idp_client()
    try:
        files = []
        file_handles = []
        for path in document_paths:
            fh = open(path, "rb")  # noqa: SIM115
            file_handles.append(fh)
            files.append(("files", (os.path.basename(path), fh, "application/pdf")))
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                resp = await client.post(
                    f"{base_url}/api/plugins/{plugin_id}/calibrate",
                    files=files,
                    headers=headers,
                )
                resp.raise_for_status()
                return json.dumps(resp.json())
        finally:
            for fh in file_handles:
                fh.close()
    except Exception as exc:
        return json.dumps({"error": f"IDP calibrate_schema failed: {exc}"})


async def _handle_idp_get_calibration_status(params: dict[str, Any]) -> str:
    """GET /api/plugins/{plugin_id}/calibrate/status with optional workflow_id."""
    import httpx

    plugin_id = params.get("plugin_id", "")
    if not plugin_id:
        return json.dumps({"error": "plugin_id is required"})

    base_url, headers = _get_idp_client()
    query: dict[str, str] = {}
    if params.get("workflow_id"):
        query["workflow_id"] = params["workflow_id"]

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{base_url}/api/plugins/{plugin_id}/calibrate/status",
                params=query,
                headers=headers,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": f"IDP get_calibration_status failed: {exc}"})


async def _handle_idp_get_settings(params: dict[str, Any]) -> str:
    """GET /api/settings."""
    import httpx

    base_url, headers = _get_idp_client()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{base_url}/api/settings", headers=headers)
            resp.raise_for_status()
            return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": f"IDP get_settings failed: {exc}"})


async def _handle_idp_update_settings(params: dict[str, Any]) -> str:
    """PUT /api/settings with optional extraction_mode, default_llm_model, active_plugin."""
    import httpx

    body: dict[str, Any] = {}
    for key in ("extraction_mode", "default_llm_model", "active_plugin"):
        if params.get(key) is not None:
            body[key] = params[key]

    base_url, headers = _get_idp_client()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.put(
                f"{base_url}/api/settings",
                json=body,
                headers=headers,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": f"IDP update_settings failed: {exc}"})


_IDP_TOOL_HANDLERS = {
    "discover_api": _handle_idp_discover_api,
    "execute_api": _handle_idp_execute_api,
    "upload_document": _handle_idp_upload_document,
    "get_job_detail": _handle_idp_get_job_detail,
    "get_job_status": _handle_idp_get_job_status,
    "list_jobs": _handle_idp_list_jobs,
    "patch_job_verdict": _handle_idp_patch_job_verdict,
    "list_plugins": _handle_idp_list_plugins,
    "get_plugin": _handle_idp_get_plugin,
    "update_schema": _handle_idp_update_schema,
    "calibrate_schema": _handle_idp_calibrate_schema,
    "get_calibration_status": _handle_idp_get_calibration_status,
    "get_settings": _handle_idp_get_settings,
    "update_settings": _handle_idp_update_settings,
}


# ---------------------------------------------------------------------------
# Ravenna (synthesizer) tool handler functions
# ---------------------------------------------------------------------------


def _get_session_store(operativo_id: str) -> SessionStore:
    """Create a SessionStore for the given operativo."""
    root = os.environ.get("STORAGE_ROOT", "/tmp/agent-harness")
    backend = LocalStorageBackend(root=root)
    return SessionStore(backend=backend, operativo_id=operativo_id)


async def _handle_read_progress(params: dict[str, Any]) -> str:
    """Read PROGRESS.md field reports for an operativo."""
    operativo_id = params.get("operativo_id", "")
    store = _get_session_store(operativo_id)
    progress = await store.read_progress()
    return progress if progress else "[No progress reports found]"


async def _handle_load_artifact(params: dict[str, Any]) -> str:
    """Load a JSON artifact from session storage."""
    operativo_id = params.get("operativo_id", "")
    artifact_name = params.get("artifact_name", "")
    root = os.environ.get("STORAGE_ROOT", "/tmp/agent-harness")
    backend = LocalStorageBackend(root=root)
    key = f"sessions/{operativo_id}/{artifact_name}"
    try:
        data = await backend.read(key)
        return data.decode("utf-8")
    except FileNotFoundError:
        return json.dumps({"error": f"Artifact not found: {artifact_name}"})


async def _handle_write_structured_result(params: dict[str, Any]) -> str:
    """Write the final structured_result.json to session storage."""
    operativo_id = params.get("operativo_id", "")
    result_json = params.get("result_json", "{}")
    root = os.environ.get("STORAGE_ROOT", "/tmp/agent-harness")
    backend = LocalStorageBackend(root=root)
    key = f"sessions/{operativo_id}/structured_result.json"
    await backend.write(key, result_json.encode("utf-8"))
    return json.dumps({"status": "written", "path": key})


async def _handle_check_caller_permission(params: dict[str, Any]) -> str:
    """Check if caller has permission to receive results.

    Currently always permits — real ACL to be implemented with auth system.
    """
    caller_id = params.get("caller_id", "")
    operativo_id = params.get("operativo_id", "")
    return json.dumps({
        "permitted": True,
        "caller_id": caller_id,
        "operativo_id": operativo_id,
    })


_RAVENNA_TOOL_HANDLERS = {
    "read_progress": _handle_read_progress,
    "load_artifact": _handle_load_artifact,
    "write_structured_result": _handle_write_structured_result,
    "check_caller_permission": _handle_check_caller_permission,
}


def build_tool_handler(
    client: AnthropicClient,
    domain: str,
    operativo_id: str | None = None,
) -> ToolHandler:
    """Build ToolHandler with domain-specific tool handlers.

    Supports 'dce' and 'idp' domains.

    Args:
        client: AnthropicClient for the tool handler.
        domain: Domain name (e.g. "dce", "idp").

    Returns:
        ToolHandler with registered tool implementations.

    Raises:
        ValueError: If domain is not supported.
    """
    if domain == "dce":
        handlers = {**_CPC_TOOL_HANDLERS, **_RAVENNA_TOOL_HANDLERS}
        if operativo_id is not None:
            base_extract = handlers["extract_pdf_text"]

            async def _extract_with_operativo(params: dict[str, Any]) -> str:
                merged = dict(params)
                merged["operativo_id"] = operativo_id
                return await base_extract(merged)

            handlers["extract_pdf_text"] = _extract_with_operativo
    elif domain == "idp":
        handlers = {**_IDP_TOOL_HANDLERS, **_RAVENNA_TOOL_HANDLERS}
        if operativo_id is not None:
            base_upload = handlers["upload_document"]

            async def _upload_with_operativo(params: dict[str, Any]) -> str:
                merged = dict(params)
                merged["operativo_id"] = operativo_id
                return await base_upload(merged)

            handlers["upload_document"] = _upload_with_operativo
    else:
        raise ValueError(f"Unsupported domain: {domain}. Supported: 'dce', 'idp'.")
    return ToolHandler(client=client, tool_handlers=handlers)


async def load_domain_memory(backend: StorageBackend, domain: str) -> str:
    """Load domain memory via DomainStore.

    Args:
        backend: Storage backend to read from.
        domain: Domain name (e.g. "dce").

    Returns:
        Domain memory content as a string.
    """
    store = DomainStore(backend=backend, domain=domain)
    return await store.read()


# ---------------------------------------------------------------------------
# Memory recall and bulletin store factories
# ---------------------------------------------------------------------------

def get_memory_recall():
    """Get or create singleton MemoryRecall with InMemoryGraphStore.

    Production: replace with PostgresGraphStore connected to pgvector.
    """
    global _memory_recall_instance
    if _memory_recall_instance is not None:
        return _memory_recall_instance

    from agent_harness.memory.embeddings import FakeEmbeddingClient
    from agent_harness.memory.graph_store import InMemoryGraphStore
    from agent_harness.memory.recall import MemoryRecall

    store = InMemoryGraphStore(embedder=FakeEmbeddingClient(dimensions=8))
    _memory_recall_instance = MemoryRecall(store=store)
    return _memory_recall_instance


# Module-level singleton for bulletin store (shared across activities in one worker)
_bulletin_store_instance = None
_memory_recall_instance = None


def get_bulletin_store():
    """Get or create singleton bulletin store.

    Returns the same InMemoryBulletinStore instance across calls within
    one worker process. Production: replace with a persistent store.
    """
    global _bulletin_store_instance
    if _bulletin_store_instance is None:
        from agent_harness.memory.bulletin_store import InMemoryBulletinStore
        _bulletin_store_instance = InMemoryBulletinStore()
    return _bulletin_store_instance
