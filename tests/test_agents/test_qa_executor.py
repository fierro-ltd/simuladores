"""Tests for SantosQAReviewer executor."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_harness.agents.qa_reviewer import (
    QAReport,
    SantosQAReviewer,
    _parse_qa_json,
)
from agent_harness.core.operativo import Severity
from agent_harness.llm.client import AnthropicClient, MessageResult, TokenUsage


def _mock_client(response_json: dict) -> AnthropicClient:
    """Create a mock AnthropicClient that returns the given JSON as content."""
    client = MagicMock(spec=AnthropicClient)
    client.send_message = AsyncMock(
        return_value=MessageResult(
            content=json.dumps(response_json),
            stop_reason="end_turn",
            tool_calls=[],
            usage=TokenUsage(input_tokens=200, output_tokens=100),
            model="claude-sonnet-4-6",
        )
    )
    return client


class TestParseQAJson:
    """Tests for _parse_qa_json helper."""

    def test_valid_checks(self):
        raw = json.dumps({
            "checks": [
                {
                    "field": "product_name",
                    "expected": "Widget A",
                    "actual": "Widget B",
                    "severity": "BLOCKING",
                    "auto_correctable": False,
                }
            ]
        })
        report = _parse_qa_json(raw, "op-123")
        assert isinstance(report, QAReport)
        assert report.operativo_id == "op-123"
        assert len(report.checks) == 1
        assert report.checks[0].severity == Severity.BLOCKING
        assert report.checks[0].auto_correctable is False

    def test_multiple_severities(self):
        raw = json.dumps({
            "checks": [
                {"field": "a", "expected": "1", "actual": "2", "severity": "BLOCKING", "auto_correctable": True},
                {"field": "b", "expected": "x", "actual": "x", "severity": "WARNING", "auto_correctable": False},
                {"field": "c", "expected": "y", "actual": "z", "severity": "INFO", "auto_correctable": False},
            ]
        })
        report = _parse_qa_json(raw, "op-456")
        assert len(report.checks) == 3
        assert report.checks[0].severity == Severity.BLOCKING
        assert report.checks[1].severity == Severity.WARNING
        assert report.checks[2].severity == Severity.INFO

    def test_empty_checks(self):
        raw = json.dumps({"checks": []})
        report = _parse_qa_json(raw, "op-empty")
        assert report.checks == []
        assert report.all_resolved is True

    def test_invalid_json_returns_empty_report(self):
        report = _parse_qa_json("not json", "op-bad")
        assert report.operativo_id == "op-bad"
        assert len(report.checks) == 0

    def test_missing_checks_key_returns_empty_report(self):
        report = _parse_qa_json(json.dumps({"results": []}), "op-bad")
        assert report.operativo_id == "op-bad"
        assert len(report.checks) == 0

    def test_unknown_severity_defaults_to_info(self):
        raw = json.dumps({
            "checks": [
                {"field": "x", "expected": "a", "actual": "b", "severity": "UNKNOWN"}
            ]
        })
        report = _parse_qa_json(raw, "op-default")
        assert report.checks[0].severity == Severity.INFO

    def test_missing_auto_correctable_defaults_false(self):
        raw = json.dumps({
            "checks": [
                {"field": "x", "expected": "a", "actual": "b", "severity": "WARNING"}
            ]
        })
        report = _parse_qa_json(raw, "op-default")
        assert report.checks[0].auto_correctable is False


class TestSantosQAReviewer:
    """Tests for SantosQAReviewer class."""

    def test_init_creates_base_agent(self):
        reviewer = SantosQAReviewer(domain="dce")
        assert reviewer.base_agent.config.name == "santos"
        assert reviewer.base_agent.config.domain == "dce"
        assert reviewer.base_agent.config.model == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_review_returns_qa_report(self):
        reviewer = SantosQAReviewer(domain="dce")
        client = _mock_client({
            "checks": [
                {
                    "field": "product_name",
                    "expected": "Widget A",
                    "actual": "Widget B",
                    "severity": "BLOCKING",
                    "auto_correctable": True,
                },
                {
                    "field": "format",
                    "expected": "PDF",
                    "actual": "pdf",
                    "severity": "INFO",
                    "auto_correctable": False,
                },
            ]
        })

        report = await reviewer.review(
            client=client,
            operativo_id="op-qa-1",
            input_snapshot_json='{"product_name": "Widget A"}',
            raw_output_json='{"product_name": "Widget B"}',
            domain_memory="DCE rules",
        )

        assert isinstance(report, QAReport)
        assert report.operativo_id == "op-qa-1"
        assert len(report.checks) == 2
        assert report.has_blocking is True

    @pytest.mark.asyncio
    async def test_review_calls_client_with_opus(self):
        reviewer = SantosQAReviewer(domain="dce")
        client = _mock_client({"checks": []})

        await reviewer.review(
            client=client,
            operativo_id="op-qa-2",
            input_snapshot_json="{}",
            raw_output_json="{}",
            domain_memory="",
        )

        client.send_message.assert_called_once()
        call_kwargs = client.send_message.call_args
        assert call_kwargs.kwargs["model"] == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_review_includes_snapshots_in_prompt(self):
        reviewer = SantosQAReviewer(domain="dce")
        client = _mock_client({"checks": []})

        await reviewer.review(
            client=client,
            operativo_id="op-qa-3",
            input_snapshot_json='{"key": "input_val"}',
            raw_output_json='{"key": "output_val"}',
            domain_memory="",
        )

        call_kwargs = client.send_message.call_args
        prompt = call_kwargs.kwargs["prompt"]
        user_messages = [m for m in prompt["messages"] if m["role"] == "user"]
        user_text = " ".join(m["content"] for m in user_messages)
        assert "input_val" in user_text
        assert "output_val" in user_text

    @pytest.mark.asyncio
    async def test_review_with_citation_matrix(self):
        reviewer = SantosQAReviewer(domain="dce")
        client = _mock_client({
            "checks": [],
            "corrected_citation_matrix": [
                {
                    "citation_text": "16CFR1252",
                    "original_verdict": "MISSING",
                    "corrected_verdict": "INVALID",
                    "corrected_rationale": "Part exists but is an exemption",
                    "correction_type": "rationale_fix",
                }
            ],
        })

        report = await reviewer.review(
            client=client,
            operativo_id="op-cit",
            input_snapshot_json="{}",
            raw_output_json="{}",
            domain_memory="",
        )

        assert len(report.corrected_citation_matrix) == 1
        assert report.corrected_citation_matrix[0]["citation_text"] == "16CFR1252"

    @pytest.mark.asyncio
    async def test_review_returns_empty_on_invalid_response(self):
        reviewer = SantosQAReviewer(domain="dce")
        client = MagicMock(spec=AnthropicClient)
        client.send_message = AsyncMock(
            return_value=MessageResult(
                content="Not JSON at all",
                stop_reason="end_turn",
                model="claude-sonnet-4-6",
            )
        )

        report = await reviewer.review(
            client=client,
            operativo_id="op-bad",
            input_snapshot_json="{}",
            raw_output_json="{}",
            domain_memory="",
        )
        assert report.operativo_id == "op-bad"
        assert len(report.checks) == 0


class TestQAReviewOutputCitationMatrix:
    """Tests for corrected_citation_matrix in QAReviewOutput."""

    def test_qa_review_output_has_citation_matrix_field(self):
        from agent_harness.activities.qa_review import QAReviewOutput
        output = QAReviewOutput(
            operativo_id="op-1",
            qa_report_json='{"checks": []}',
            corrections_applied=0,
            final_status="COMPLETED",
            phase_result="done",
            corrected_citation_matrix_json="[]",
        )
        assert output.corrected_citation_matrix_json == "[]"

    def test_qa_review_output_defaults_empty(self):
        from agent_harness.activities.qa_review import QAReviewOutput
        output = QAReviewOutput(
            operativo_id="op-1",
            qa_report_json='{"checks": []}',
            corrections_applied=0,
            final_status="COMPLETED",
            phase_result="done",
        )
        assert output.corrected_citation_matrix_json == ""


class TestParseQAJsonCitationMatrix:
    """Tests for corrected_citation_matrix parsing."""

    def test_parse_includes_citation_matrix(self):
        raw = json.dumps({
            "checks": [],
            "corrected_citation_matrix": [
                {
                    "citation_text": "16CFR1252",
                    "original_verdict": "MISSING",
                    "corrected_verdict": "INVALID",
                    "corrected_rationale": "Part exists but is an exemption determination, not certifiable",
                    "correction_type": "rationale_fix",
                }
            ],
        })
        report = _parse_qa_json(raw, "op-cit")
        assert len(report.corrected_citation_matrix) == 1
        assert report.corrected_citation_matrix[0]["citation_text"] == "16CFR1252"
        assert report.corrected_citation_matrix[0]["correction_type"] == "rationale_fix"

    def test_parse_missing_citation_matrix_defaults_empty(self):
        raw = json.dumps({"checks": []})
        report = _parse_qa_json(raw, "op-no-cit")
        assert report.corrected_citation_matrix == []

    def test_parse_invalid_json_has_empty_matrix(self):
        report = _parse_qa_json("not json", "op-bad")
        assert report.corrected_citation_matrix == []
