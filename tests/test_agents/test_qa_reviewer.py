"""Tests for Santos QA reviewer."""

from unittest.mock import AsyncMock, patch

import pytest

from agent_harness.agents.qa_reviewer import (
    SANTOS_QA_IDENTITY,
    QACheck,
    QAReport,
    SantosQAReviewer,
)
from agent_harness.core.operativo import Severity
from agent_harness.llm.client import MessageResult, TokenUsage


class TestSantosQAIdentity:
    def test_mentions_santos(self):
        assert "Santos" in SANTOS_QA_IDENTITY

    def test_mentions_qa(self):
        assert "Quality Assurance" in SANTOS_QA_IDENTITY or "QA" in SANTOS_QA_IDENTITY

    def test_mentions_blocking(self):
        assert "BLOCKING" in SANTOS_QA_IDENTITY

    def test_mentions_auto_correction(self):
        assert "correction" in SANTOS_QA_IDENTITY.lower()

    def test_mentions_max_attempts(self):
        assert "3" in SANTOS_QA_IDENTITY


class TestQACheck:
    def test_creation(self):
        check = QACheck(
            field="product_name",
            expected="Widget A",
            actual="Widget B",
            severity=Severity.BLOCKING,
            auto_correctable=False,
        )
        assert check.field == "product_name"
        assert check.severity == Severity.BLOCKING

    def test_frozen(self):
        check = QACheck("f", "e", "a", Severity.INFO, True)
        with pytest.raises(AttributeError):
            check.severity = Severity.WARNING


class TestQAReport:
    def test_empty_report(self):
        report = QAReport(operativo_id="op-123")
        assert report.has_blocking is False
        assert report.all_resolved is True
        assert report.can_retry is False

    def test_blocking_issue(self):
        report = QAReport(
            operativo_id="op-123",
            checks=[
                QACheck("name", "A", "B", Severity.BLOCKING, True),
            ],
        )
        assert report.has_blocking is True
        assert report.all_resolved is False
        assert report.can_retry is True

    def test_only_warnings(self):
        report = QAReport(
            operativo_id="op-123",
            checks=[
                QACheck("fmt", "a", "b", Severity.WARNING, True),
            ],
        )
        assert report.has_blocking is False
        assert report.all_resolved is True

    def test_max_retries_exhausted(self):
        report = QAReport(
            operativo_id="op-123",
            checks=[QACheck("x", "a", "b", Severity.BLOCKING, True)],
            correction_attempts=3,
            max_attempts=3,
        )
        assert report.can_retry is False

    def test_can_retry_with_attempts_remaining(self):
        report = QAReport(
            operativo_id="op-123",
            checks=[QACheck("x", "a", "b", Severity.BLOCKING, True)],
            correction_attempts=1,
        )
        assert report.can_retry is True


# --- Checklist injection tests ---

_VALID_QA_JSON = '{"checks": [{"field": "product_name", "expected": "A", "actual": "A", "severity": "INFO", "auto_correctable": false}]}'


class TestSantosQAReviewerChecklist:
    """Tests that verify_checklist is properly injected into the QA prompt."""

    @pytest.mark.asyncio
    async def test_review_injects_checklist_into_prompt(self):
        """When a checklist is provided the prompt must contain each item."""
        reviewer = SantosQAReviewer(domain="dce")
        checklist = [
            "Check field A",
            "Check field B",
        ]

        captured_prompt: dict | None = None

        async def _fake_send(*, prompt, model, **kwargs):
            nonlocal captured_prompt
            captured_prompt = prompt
            return MessageResult(
                content=_VALID_QA_JSON,
                stop_reason="end_turn",
                usage=TokenUsage(),
            )

        mock_client = AsyncMock()
        mock_client.send_message = _fake_send

        await reviewer.review(
            client=mock_client,
            operativo_id="op-42",
            input_snapshot_json='{"product": "X"}',
            raw_output_json='{"product": "X"}',
            domain_memory="",
            verify_checklist=checklist,
        )

        # Find the user message content in the prompt
        assert captured_prompt is not None
        messages = captured_prompt.get("messages", [])
        user_content = " ".join(
            m["content"] for m in messages if m.get("role") == "user"
        )
        assert "## Mandatory Verification Checklist" in user_content
        assert "- [ ] Check field A" in user_content
        assert "- [ ] Check field B" in user_content

    @pytest.mark.asyncio
    async def test_review_without_checklist_has_no_checklist_section(self):
        """When no checklist is provided the prompt must NOT contain the section."""
        reviewer = SantosQAReviewer(domain="dce")

        captured_prompt: dict | None = None

        async def _fake_send(*, prompt, model, **kwargs):
            nonlocal captured_prompt
            captured_prompt = prompt
            return MessageResult(
                content=_VALID_QA_JSON,
                stop_reason="end_turn",
                usage=TokenUsage(),
            )

        mock_client = AsyncMock()
        mock_client.send_message = _fake_send

        await reviewer.review(
            client=mock_client,
            operativo_id="op-42",
            input_snapshot_json='{"product": "X"}',
            raw_output_json='{"product": "X"}',
            domain_memory="",
        )

        assert captured_prompt is not None
        messages = captured_prompt.get("messages", [])
        user_content = " ".join(
            m["content"] for m in messages if m.get("role") == "user"
        )
        assert "## Mandatory Verification Checklist" not in user_content

    @pytest.mark.asyncio
    async def test_review_with_empty_checklist_has_no_checklist_section(self):
        """An empty list should behave the same as None."""
        reviewer = SantosQAReviewer(domain="dce")

        captured_prompt: dict | None = None

        async def _fake_send(*, prompt, model, **kwargs):
            nonlocal captured_prompt
            captured_prompt = prompt
            return MessageResult(
                content=_VALID_QA_JSON,
                stop_reason="end_turn",
                usage=TokenUsage(),
            )

        mock_client = AsyncMock()
        mock_client.send_message = _fake_send

        await reviewer.review(
            client=mock_client,
            operativo_id="op-42",
            input_snapshot_json='{"product": "X"}',
            raw_output_json='{"product": "X"}',
            domain_memory="",
            verify_checklist=[],
        )

        assert captured_prompt is not None
        messages = captured_prompt.get("messages", [])
        user_content = " ".join(
            m["content"] for m in messages if m.get("role") == "user"
        )
        assert "## Mandatory Verification Checklist" not in user_content
