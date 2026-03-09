"""Tests for cortex_generate_bulletin activity."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agent_harness.memory.bulletin import Bulletin
from agent_harness.workflows.cortex import CortexScheduleInput


class TestCortexGenerateBulletin:
    """Test the cortex_generate_bulletin activity."""

    @pytest.mark.asyncio
    async def test_returns_dict_with_required_keys(self) -> None:
        from agent_harness.activities.implementations import cortex_generate_bulletin

        input_data = CortexScheduleInput(domain="dce", max_patterns=5, max_tokens=100)

        with patch(
            "agent_harness.activities.implementations.get_anthropic_client"
        ), patch(
            "agent_harness.activities.implementations.get_memory_recall"
        ), patch(
            "agent_harness.activities.implementations.generate_bulletin"
        ) as mock_gen:
            mock_gen.return_value = Bulletin(
                domain="dce",
                summary="DCE patterns show common issues with lab accreditation.",
                pattern_count=2,
                generated_at="2026-02-22T12:00:00+00:00",
            )

            result = await cortex_generate_bulletin(input_data)

        assert "domain" in result
        assert result["domain"] == "dce"
        assert "pattern_count" in result
        assert result["pattern_count"] == 2
        assert "bulletin_summary" in result
        assert len(result["bulletin_summary"]) > 0
        assert "generated_at" in result

    @pytest.mark.asyncio
    async def test_empty_patterns_returns_empty_summary(self) -> None:
        from agent_harness.activities.implementations import cortex_generate_bulletin

        input_data = CortexScheduleInput(domain="dce")

        with patch(
            "agent_harness.activities.implementations.get_anthropic_client"
        ) as mock_get_client, patch(
            "agent_harness.activities.implementations.get_memory_recall"
        ), patch(
            "agent_harness.activities.implementations.generate_bulletin"
        ) as mock_gen:
            mock_gen.return_value = Bulletin(
                domain="dce",
                summary="",
                pattern_count=0,
                generated_at="2026-02-22T12:00:00+00:00",
            )

            result = await cortex_generate_bulletin(input_data)

        assert result["pattern_count"] == 0
        assert result["bulletin_summary"] == ""

    @pytest.mark.asyncio
    async def test_generated_at_is_iso_format(self) -> None:
        """generated_at must be a valid ISO 8601 timestamp."""
        from datetime import datetime

        from agent_harness.activities.implementations import cortex_generate_bulletin

        input_data = CortexScheduleInput(domain="dce")

        with patch(
            "agent_harness.activities.implementations.get_anthropic_client"
        ), patch(
            "agent_harness.activities.implementations.get_memory_recall"
        ), patch(
            "agent_harness.activities.implementations.generate_bulletin"
        ) as mock_gen:
            mock_gen.return_value = Bulletin(
                domain="dce",
                summary="",
                pattern_count=0,
                generated_at="2026-02-22T12:00:00+00:00",
            )

            result = await cortex_generate_bulletin(input_data)

        # Should not raise
        datetime.fromisoformat(result["generated_at"])

    @pytest.mark.asyncio
    async def test_passes_config_to_generate_bulletin(self) -> None:
        """Verify max_patterns and max_tokens are forwarded to BulletinConfig."""
        from agent_harness.activities.implementations import cortex_generate_bulletin

        input_data = CortexScheduleInput(domain="dce", max_patterns=10, max_tokens=200)

        with patch(
            "agent_harness.activities.implementations.get_anthropic_client"
        ), patch(
            "agent_harness.activities.implementations.get_memory_recall"
        ), patch(
            "agent_harness.activities.implementations.generate_bulletin"
        ) as mock_gen:
            mock_gen.return_value = Bulletin(
                domain="dce",
                summary="test summary",
                pattern_count=3,
                generated_at="2026-02-22T00:00:00+00:00",
            )

            result = await cortex_generate_bulletin(input_data)

            # Verify generate_bulletin was called with correct config
            call_kwargs = mock_gen.call_args
            config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
            assert config.domain == "dce"
            assert config.max_patterns == 10
            assert config.max_tokens == 200

        assert result["domain"] == "dce"
        assert result["bulletin_summary"] == "test summary"

    @pytest.mark.asyncio
    async def test_client_and_recall_passed_to_generate_bulletin(self) -> None:
        """Verify get_anthropic_client and get_memory_recall results are forwarded."""
        from agent_harness.activities.implementations import cortex_generate_bulletin

        input_data = CortexScheduleInput(domain="dce")

        mock_client = AsyncMock()
        mock_recall = AsyncMock()

        with patch(
            "agent_harness.activities.implementations.get_anthropic_client",
            return_value=mock_client,
        ), patch(
            "agent_harness.activities.implementations.get_memory_recall",
            return_value=mock_recall,
        ), patch(
            "agent_harness.activities.implementations.generate_bulletin"
        ) as mock_gen:
            mock_gen.return_value = Bulletin(
                domain="dce",
                summary="",
                pattern_count=0,
                generated_at="2026-02-22T00:00:00+00:00",
            )

            await cortex_generate_bulletin(input_data)

            # Verify client and recall are forwarded
            call_kwargs = mock_gen.call_args
            assert call_kwargs.kwargs["client"] is mock_client
            assert call_kwargs.kwargs["recall"] is mock_recall


class TestCortexWorkerRegistration:
    """Verify cortex activity and workflow are registered in DCE worker."""

    def test_cortex_activity_in_activity_list(self) -> None:
        from agent_harness.workers.dce import get_activity_list

        activities = get_activity_list()
        activity_names = [a.__name__ for a in activities]
        assert "cortex_generate_bulletin" in activity_names

    def test_cortex_workflow_in_workflow_list(self) -> None:
        from agent_harness.workers.dce import get_workflow_list
        from agent_harness.workflows.cortex import CortexBulletinWorkflow

        workflows = get_workflow_list()
        assert CortexBulletinWorkflow in workflows
