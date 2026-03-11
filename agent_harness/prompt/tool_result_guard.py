"""Tool result sanitization guard.

Scans tool outputs before they are fed back into agent context.
Prevents MCP tool-result injection where a compromised tool returns
content designed to manipulate the LLM (e.g., "ignore previous",
"new instructions", exfiltration directives).

Clean results pass through unchanged. Suspicious results are redacted
and flagged with the reason.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SanitizedResult:
    """Result of sanitizing a tool output."""

    content: str
    was_sanitized: bool
    reason: str = ""


# Patterns that indicate tool-result injection attempts
_TOOL_RESULT_PATTERNS: list[tuple[str, str]] = [
    (r"ignore\s+previous", "ignore previous instructions"),
    (r"new\s+instructions", "new instructions injection"),
    (r"system\s+prompt", "system prompt extraction"),
    (r"exfiltrate", "exfiltration attempt"),
    (r"base64\.decode", "base64 decode injection"),
]


def sanitize_tool_result(
    result: str,
    tool_name: str = "",
    domain: str = "",
) -> SanitizedResult:
    """Sanitize a tool result before feeding it into agent context.

    Args:
        result: The raw tool output string.
        tool_name: Name of the tool that produced the result.
        domain: Domain context (e.g., "dce", "idp").

    Returns:
        SanitizedResult with original or redacted content.
    """
    if not result:
        return SanitizedResult(content=result, was_sanitized=False)

    for pattern, reason in _TOOL_RESULT_PATTERNS:
        if re.search(pattern, result, re.IGNORECASE):
            redacted = f"[REDACTED: tool result from '{tool_name}' contained suspicious content — {reason}]"
            return SanitizedResult(
                content=redacted,
                was_sanitized=True,
                reason=reason,
            )

    return SanitizedResult(content=result, was_sanitized=False)
