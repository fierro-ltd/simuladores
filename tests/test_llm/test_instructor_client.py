"""Tests for the instructor client factory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import instructor
import pytest

from agent_harness.llm.instructor_client import create_instructor_client


class TestCreateInstructorClient:
    """Tests for create_instructor_client factory."""

    @patch("agent_harness.llm.instructor_client.instructor")
    @patch("agent_harness.llm.instructor_client.AsyncAnthropicVertex")
    def test_returns_patched_client(
        self, mock_vertex_cls: MagicMock, mock_instructor: MagicMock
    ) -> None:
        """Factory creates vertex client and wraps it with instructor."""
        mock_vertex_instance = MagicMock()
        mock_vertex_cls.return_value = mock_vertex_instance
        mock_patched = MagicMock(spec=instructor.AsyncInstructor)
        mock_instructor.from_anthropic.return_value = mock_patched

        client = create_instructor_client(project_id="test-proj", region="us-east1")

        assert client is mock_patched
        mock_vertex_cls.assert_called_once()
        call_kwargs = mock_vertex_cls.call_args[1]
        assert call_kwargs["project_id"] == "test-proj"
        assert call_kwargs["region"] == "us-east1"
        mock_instructor.from_anthropic.assert_called_once_with(mock_vertex_instance)

    @patch("agent_harness.llm.instructor_client.instructor")
    @patch("agent_harness.llm.instructor_client.AsyncAnthropicVertex")
    @patch("agent_harness.llm.instructor_client.load_config")
    def test_reads_from_config_when_no_args(
        self,
        mock_load_config: MagicMock,
        mock_vertex_cls: MagicMock,
        mock_instructor: MagicMock,
    ) -> None:
        """Falls back to load_config() when project_id/region are not provided."""
        mock_cfg = MagicMock()
        mock_cfg.vertex.project_id = "config-proj"
        mock_cfg.vertex.region = "europe-west1"
        mock_load_config.return_value = mock_cfg
        mock_vertex_cls.return_value = MagicMock()
        mock_instructor.from_anthropic.return_value = MagicMock(
            spec=instructor.AsyncInstructor
        )

        client = create_instructor_client()

        mock_load_config.assert_called_once()
        call_kwargs = mock_vertex_cls.call_args[1]
        assert call_kwargs["project_id"] == "config-proj"
        assert call_kwargs["region"] == "europe-west1"

    @patch("agent_harness.llm.instructor_client.instructor")
    @patch("agent_harness.llm.instructor_client.AsyncAnthropicVertex")
    @patch("agent_harness.llm.instructor_client.load_config")
    def test_partial_args_fall_back_to_config(
        self,
        mock_load_config: MagicMock,
        mock_vertex_cls: MagicMock,
        mock_instructor: MagicMock,
    ) -> None:
        """When only project_id is given, region falls back to config."""
        mock_cfg = MagicMock()
        mock_cfg.vertex.region = "asia-southeast1"
        mock_load_config.return_value = mock_cfg
        mock_vertex_cls.return_value = MagicMock()
        mock_instructor.from_anthropic.return_value = MagicMock(
            spec=instructor.AsyncInstructor
        )

        create_instructor_client(project_id="explicit-proj")

        call_kwargs = mock_vertex_cls.call_args[1]
        assert call_kwargs["project_id"] == "explicit-proj"
        assert call_kwargs["region"] == "asia-southeast1"
