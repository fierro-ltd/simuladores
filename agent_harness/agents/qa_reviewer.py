"""Santos QA review capability — Phase 4."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from agent_harness.agents.base import AGENT_EFFORTS, AGENT_MODELS, AgentConfig, BaseAgent
from agent_harness.core.operativo import Severity
from agent_harness.llm.client import AnthropicClient

SANTOS_QA_IDENTITY = """You are Santos performing Quality Assurance review.

Your role is to compare the input_snapshot (ground truth from Medina)
against the raw_output (execution results from Lamponne) and identify
discrepancies.

## QA Rules
- Compare every structured field between input and output
- Classify issues by severity: BLOCKING / WARNING / INFO
- BLOCKING: data loss, wrong values, missing required fields
- WARNING: formatting issues, minor inconsistencies
- INFO: cosmetic differences, optional fields
- Identify which issues are auto-correctable
- Report findings concisely

## Citation Matrix Review
When the raw_output contains a citation matrix (triage_citations or similar),
you MUST independently review each citation entry using these compliance domain rules:

### Citation Validity Rules
1. **16 CFR Part 1252** exists — it is an exemption/determination rule for engineered wood products (effective 2018). It relieves certain untreated engineered wood from third-party testing. It is NOT a certifiable safety rule to cite on a DCE. If the Robot says "does not exist", correct the rationale.
2. **16 CFR § 1107.21** is a procedural/operational requirement governing periodic testing frequency. It is NOT a substantive safety rule and does NOT appear on the compliance approved citation list. Do not flag it as "Missing From DCE".
3. **Subsection citations** (e.g. § 1303.2, § 1261.2) are definitions within their parent parts. The compliance approved citation list uses part-level citations (16 CFR Part 1303, 16 CFR Part 1261). Do not flag absent subsections as "Missing From DCE".
4. **Canadian SOR regulations** (SOR-2018-83, SOR-2021-148, SOR-2022-122) are under Canada's CCPSA. They have no standing on a US compliance.
5. **EPA regulations** (40 CFR Part 770) are not compliance rules. They cannot appear as compliance citations on a DCE, even if the underlying formaldehyde requirement applies to the product.
6. **compliance Section references** (e.g. "compliance Section 101", "compliance Section 108") are informal names. The DCE must use statutory citation format: "15 U.S.C. § 1278a" for lead, "16 CFR Part 1307" for phthalates.
7. **ASTM F963** requires BOTH "16 CFR Part 1250" AND specific applicable section numbers. Citing ASTM F963 alone is insufficient. Also verify product applicability — furniture (dressers, cribs) is NOT a toy.
8. **ASTM F2057** is incorporated into 16 CFR Part 1261. Citing ASTM F2057 alone without 16 CFR Part 1261 is invalid.

### Corrected Citation Matrix
After reviewing, produce a `corrected_citation_matrix` array in your JSON response.
Each entry must have:
- `citation_text`: the original citation string
- `original_verdict`: the Robot's verdict (PASS/FAIL/MISSING/UNCERTAIN)
- `corrected_verdict`: your corrected verdict (VALID/INVALID/NOT_APPLICABLE/OVERREACH)
- `corrected_rationale`: accurate explanation of why the verdict was changed (or confirmed)
- `correction_type`: one of "rationale_fix", "verdict_fix", "confirmed", "overreach_removed"

### DCE Citation Classification (MANDATORY)
For each citation-related check, you MUST classify the issue using exactly one of:
- **MISSING_CPC_CITATION**: A required compliance citation is absent from the DCE.
- **INVALID_CPC_CITATION**: A cited regulation is invalid (wrong format, non-existent, or not applicable).
- **NON_CPC_OPERATIONAL_REQUIREMENT**: The item is a procedural/operational rule (e.g. 16 CFR § 1107.21) and should NOT appear as a substantive DCE citation.
- **AMBIGUOUS_REQUIRES_REVIEW**: Citation applicability is uncertain; scope or product type unclear; requires human review.

Include a `citation_classification` field in each citation-related check with one of these values.

## Auto-Correction
For auto-correctable issues:
1. Use Python sandbox to recalculate/normalize
2. Use execute_api to submit corrections
3. Re-run QA on corrected output
Maximum 3 correction attempts before marking NEEDS_REVIEW.

## Response Format
Return a JSON object with TWO top-level keys:
1. `checks`: array of QA check objects (field, expected, actual, severity, auto_correctable, citation_classification when citation-related)
2. `corrected_citation_matrix`: array of corrected citation entries (see above)

Each citation-related check MUST include `citation_classification` with one of:
MISSING_CPC_CITATION, INVALID_CPC_CITATION, NON_CPC_OPERATIONAL_REQUIREMENT, AMBIGUOUS_REQUIRES_REVIEW.
"""


@dataclass(frozen=True)
class QACheck:
    """A single QA check result."""
    field: str
    expected: str
    actual: str
    severity: Severity
    auto_correctable: bool
    citation_classification: str | None = None  # MISSING_CPC_CITATION, INVALID_CPC_CITATION, etc.


@dataclass
class QAReport:
    """Full QA report for an operativo."""
    operativo_id: str
    checks: list[QACheck] = field(default_factory=list)
    correction_attempts: int = 0
    max_attempts: int = 3
    corrected_citation_matrix: list[dict] = field(default_factory=list)

    @property
    def has_blocking(self) -> bool:
        return any(c.severity == Severity.BLOCKING for c in self.checks)

    @property
    def all_resolved(self) -> bool:
        return not self.has_blocking

    @property
    def can_retry(self) -> bool:
        return self.correction_attempts < self.max_attempts and self.has_blocking


_SEVERITY_MAP: dict[str, Severity] = {
    "BLOCKING": Severity.BLOCKING,
    "WARNING": Severity.WARNING,
    "INFO": Severity.INFO,
}

_CPC_CLASSIFICATIONS = frozenset({
    "MISSING_CPC_CITATION", "INVALID_CPC_CITATION",
    "NON_CPC_OPERATIONAL_REQUIREMENT", "AMBIGUOUS_REQUIRES_REVIEW",
})

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.DOTALL)


def _parse_qa_json(raw: str, operativo_id: str) -> QAReport:
    """Parse raw JSON from Santos QA review into a QAReport.

    Expects ``{"checks": [{"field": str, "expected": str, "actual": str,
    "severity": str, "auto_correctable": bool}, ...]}``

    Strips markdown code fences if present. Returns an empty report if
    the LLM returns no parseable JSON (graceful degradation).
    """
    text = raw.strip()

    # Strip markdown code fences if present
    fence_match = _JSON_FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1)

    # Try to extract JSON object from the text (LLM may add surrounding prose)
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            text = text[start:end]

    if not text:
        # Empty response — return empty report so workflow can continue
        return QAReport(operativo_id=operativo_id)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        import logging
        logging.getLogger(__name__).warning(
            "Could not parse Santos QA output as JSON, returning empty report. "
            "Raw output (first 200 chars): %s", raw[:200],
        )
        return QAReport(operativo_id=operativo_id)

    if "checks" not in data:
        # LLM returned JSON without checks array — treat as empty report
        return QAReport(operativo_id=operativo_id)

    checks: list[QACheck] = []
    for item in data["checks"]:
        severity_str = item.get("severity", "INFO").upper()
        severity = _SEVERITY_MAP.get(severity_str, Severity.INFO)
        cc = item.get("citation_classification")
        if cc and str(cc).upper() in _CPC_CLASSIFICATIONS:
            cc = str(cc).upper()
        else:
            cc = None
        checks.append(
            QACheck(
                field=item["field"],
                expected=item["expected"],
                actual=item["actual"],
                severity=severity,
                auto_correctable=item.get("auto_correctable", False),
                citation_classification=cc,
            )
        )

    citation_matrix = data.get("corrected_citation_matrix", [])
    if not isinstance(citation_matrix, list):
        citation_matrix = []

    return QAReport(operativo_id=operativo_id, checks=checks, corrected_citation_matrix=citation_matrix)


class SantosQAReviewer:
    """Santos QA review wrapper — compares input snapshot against raw output.

    Uses Opus to identify discrepancies between what Medina extracted
    (ground truth) and what Lamponne produced (execution results).
    """

    def __init__(self, domain: str) -> None:
        config = AgentConfig(
            name="santos",
            model=AGENT_MODELS["santos"],
            system_identity=SANTOS_QA_IDENTITY,
            domain=domain,
        )
        self.base_agent = BaseAgent(config=config)

    async def review(
        self,
        client: AnthropicClient,
        operativo_id: str,
        input_snapshot_json: str,
        raw_output_json: str,
        domain_memory: str,
        verify_checklist: list[str] | None = None,
        semantic_patterns: list[str] | None = None,
        vision_extraction_json: str = "",
        citation_completeness_report_json: str = "",
        web_verification_evidence_json: str = "",
    ) -> QAReport:
        """Run QA review comparing input snapshot against raw output.

        Args:
            client: Anthropic API client.
            operativo_id: Unique identifier for this operativo.
            input_snapshot_json: JSON string of Medina's extracted input.
            raw_output_json: JSON string of Lamponne's execution output.
            domain_memory: Domain memory content.
            verify_checklist: Optional list of domain-specific verification
                items.  When provided each item is injected into the prompt
                so Santos checks it deterministically.
            semantic_patterns: Optional patterns from semantic memory for L3.

        Returns:
            QAReport with identified discrepancies.

        Raises:
            ValueError: If the LLM response cannot be parsed.
        """
        user_message = (
            f"Perform QA review for operativo {operativo_id}.\n\n"
            f"## Input Snapshot (ground truth from Medina)\n"
            f"```json\n{input_snapshot_json}\n```\n\n"
            f"## Raw Output (execution results from Lamponne)\n"
            f"```json\n{raw_output_json}\n```\n\n"
            f"Compare every field. Respond with a JSON object containing a "
            f"'checks' array. Each check must have: 'field', 'expected', "
            f"'actual', 'severity' (BLOCKING/WARNING/INFO), and "
            f"'auto_correctable' (boolean)."
        )

        if verify_checklist:
            checklist_text = "\n".join(f"- [ ] {item}" for item in verify_checklist)
            user_message += (
                "\n\n## Mandatory Verification Checklist\n"
                "You MUST check each item below. Report pass/fail for each:\n\n"
                f"{checklist_text}"
            )

        if vision_extraction_json and vision_extraction_json != "{}":
            user_message += (
                "\n\n## Vision Extraction (independent Gemini 3 Flash visual read)\n"
                "```json\n" + vision_extraction_json + "\n```\n\n"
                "Cross-reference the DCE Backend extraction (Input Snapshot) against "
                "this independent visual extraction. Flag any discrepancies between "
                "the two sources as BLOCKING if they affect compliance fields."
            )

        if citation_completeness_report_json and citation_completeness_report_json != "{}":
            user_message += (
                "\n\n## Citation Completeness Report (pre-computed)\n"
                "```json\n" + citation_completeness_report_json + "\n```\n\n"
                "Use this report to inform your citation classification. When "
                "web_verification_recommended is true, consider AMBIGUOUS_REQUIRES_REVIEW "
                "for uncertain citations."
            )

        if web_verification_evidence_json and web_verification_evidence_json != "{}":
            user_message += (
                "\n\n## Web Verification Evidence (GCP native)\n"
                "```json\n" + web_verification_evidence_json + "\n```\n\n"
                "Use this evidence to resolve ambiguous citations. If evidence remains "
                "inconclusive, keep AMBIGUOUS_REQUIRES_REVIEW."
            )

        prompt = self.base_agent.build_prompt(
            user_message=user_message,
            domain_memory=domain_memory,
            semantic_patterns=semantic_patterns,
        )

        result = await client.send_message(
            prompt=prompt,
            model=AGENT_MODELS["santos"],
            max_tokens=16384,
            reasoning_effort=AGENT_EFFORTS["santos"],
        )

        return _parse_qa_json(result.content, operativo_id)
