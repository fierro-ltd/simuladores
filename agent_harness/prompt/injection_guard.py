"""Medina's injection scanner.

Pre-execution scan on all extracted document content before any field
is passed to Santos or Lamponne. On HIGH risk: halt extraction,
flag to Santos. Never silently pass injected content downstream.

Patterns cover:
- Direct phrase injection
- Imperative commands targeting agent behaviour
- Role reassignment attempts
- Exfiltration directives
- Base64-encoded payloads
- Unicode homoglyph obfuscation
"""

from __future__ import annotations

import base64
import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum


class InjectionRisk(StrEnum):
    NONE = "none"
    LOW = "low"
    HIGH = "high"


@dataclass(frozen=True)
class InjectionResult:
    risk: InjectionRisk
    matched_pattern: str = ""
    raw_match: str = ""


# Homoglyph mapping: common Cyrillic/Greek lookalikes -> Latin
_HOMOGLYPH_MAP = str.maketrans({
    "\u0430": "a",  # Cyrillic a
    "\u0435": "e",  # Cyrillic e
    "\u043e": "o",  # Cyrillic o
    "\u0440": "p",  # Cyrillic p
    "\u0441": "c",  # Cyrillic c
    "\u0443": "y",  # Cyrillic y
    "\u0445": "x",  # Cyrillic x
    "\u0456": "i",  # Cyrillic i
    "\u0458": "j",  # Cyrillic j
    "\u03bf": "o",  # Greek omicron
    "\u03b1": "a",  # Greek alpha
    "\u03b5": "e",  # Greek epsilon
    "\u0391": "A",  # Greek Alpha
    "\u0392": "B",  # Greek Beta
    "\u0395": "E",  # Greek Epsilon
})

# Phrases that trigger HIGH risk (case-insensitive)
_PHRASE_PATTERNS: list[tuple[str, str]] = [
    (r"ignore\s+previous", "ignore previous"),
    (r"you\s+are\s+now", "you are now"),
    (r"new\s+instructions", "new instructions"),
    (r"override", "override"),
    (r"disregard", "disregard"),
    (r"system\s*:\s*", "system role injection"),
    (r"\[INST\]", "instruction format injection"),
    (r"<\|im_start\|>", "ChatML injection"),
    (r"assistant\s*:\s*", "assistant role confusion"),
]

# Imperative commands
_IMPERATIVE_PATTERNS: list[tuple[str, str]] = [
    (r"\bforget\b", "forget"),
    (r"\breveal\b", "reveal"),
    (r"\bexecute\b", "execute"),
]

# Role reassignment
_ROLE_PATTERNS: list[tuple[str, str]] = [
    (r"you\s+are\s+a\b", "you are a"),
    (r"act\s+as\b", "act as"),
    (r"pretend\s+you\s+are", "pretend you are"),
    (r"your\s+new\s+identity", "your new identity"),
]

# Exfiltration
_EXFIL_PATTERNS: list[tuple[str, str]] = [
    (r"send\s+(this|the|all)\s+(data|content|info)", "send data"),
    (r"\bcurl\b", "curl"),
    (r"\bemail\b.*\b(to|the)\b", "email exfiltration"),
    (r"\bupload\b", "upload"),
    (r"POST\s+to", "POST to"),
]

ALL_PATTERNS = _PHRASE_PATTERNS + _IMPERATIVE_PATTERNS + _ROLE_PATTERNS + _EXFIL_PATTERNS


def _normalize_homoglyphs(text: str) -> str:
    """Replace common Unicode homoglyphs with their Latin equivalents."""
    return text.translate(_HOMOGLYPH_MAP)


def _check_base64_payloads(text: str) -> InjectionResult | None:
    """Detect Base64-encoded injection attempts."""
    b64_pattern = re.compile(r"[A-Za-z0-9+/]{20,}={0,2}")
    for match in b64_pattern.finditer(text):
        try:
            decoded = base64.b64decode(match.group()).decode("utf-8", errors="ignore").lower()
            for pattern, name in ALL_PATTERNS:
                if re.search(pattern, decoded, re.IGNORECASE):
                    return InjectionResult(
                        risk=InjectionRisk.HIGH,
                        matched_pattern=f"base64({name})",
                        raw_match=match.group()[:50],
                    )
        except Exception:
            continue
    return None


def scan_content(text: str) -> InjectionResult:
    """Scan extracted document content for prompt injection attempts.

    Returns InjectionResult with risk level and matched pattern.
    On HIGH risk, the caller must halt extraction and flag to Santos.
    """
    if not text:
        return InjectionResult(risk=InjectionRisk.NONE)

    # Normalize homoglyphs before pattern matching
    normalized = _normalize_homoglyphs(text)

    # Check all patterns against normalized text
    for pattern, name in ALL_PATTERNS:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            return InjectionResult(
                risk=InjectionRisk.HIGH,
                matched_pattern=name,
                raw_match=match.group(),
            )

    # Check for Base64-encoded payloads
    b64_result = _check_base64_payloads(text)
    if b64_result:
        return b64_result

    return InjectionResult(risk=InjectionRisk.NONE)


# Severity ordering for StrEnum-based InjectionRisk
_RISK_SEVERITY: dict[InjectionRisk, int] = {
    InjectionRisk.NONE: 0,
    InjectionRisk.LOW: 1,
    InjectionRisk.HIGH: 2,
}


def scan_metadata(metadata: dict[str, str]) -> InjectionResult:
    """Scan PDF metadata fields for injection patterns.

    Scans Title, Author, Subject, Keywords, Creator, and Producer fields.
    Returns the highest-risk result found across all fields.

    Args:
        metadata: Dict of PDF metadata field names to values.

    Returns:
        InjectionResult with the highest risk level found.
    """
    SCANNABLE_FIELDS = {"title", "author", "subject", "keywords", "creator", "producer"}

    highest_risk = InjectionResult(risk=InjectionRisk.NONE)

    for field_name, value in metadata.items():
        if field_name.lower() not in SCANNABLE_FIELDS:
            continue
        if not value or not isinstance(value, str):
            continue
        result = scan_content(value)
        if _RISK_SEVERITY[result.risk] > _RISK_SEVERITY[highest_risk.risk]:
            highest_risk = InjectionResult(
                risk=result.risk,
                matched_pattern=f"metadata.{field_name}: {result.matched_pattern}",
                raw_match=result.raw_match,
            )

    return highest_risk


def scan_document(text: str, metadata: dict[str, str] | None = None) -> InjectionResult:
    """Scan document text AND metadata for injection patterns.

    Returns the highest-risk result found across text content and metadata.

    Args:
        text: Document text content.
        metadata: Optional dict of PDF metadata field names to values.

    Returns:
        InjectionResult with the highest risk level found.
    """
    content_result = scan_content(text)
    if metadata is None:
        return content_result

    metadata_result = scan_metadata(metadata)

    if _RISK_SEVERITY[metadata_result.risk] > _RISK_SEVERITY[content_result.risk]:
        return metadata_result
    return content_result
