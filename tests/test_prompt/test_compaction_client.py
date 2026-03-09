"""Tests for compaction client."""

import pytest

from agent_harness.prompt.compaction_client import (
    CompactionClient,
    CompactionRequest,
    CompactionResult,
)
from agent_harness.prompt.compactor import CompactionConfig, CompactionStrategy


class TestCompactionRequest:
    def test_defaults(self):
        req = CompactionRequest()
        assert req.model == "compact-2026-01-12"
        assert req.system_prompt == ""
        assert req.messages == []
        assert req.protected_content == []

    def test_with_values(self):
        req = CompactionRequest(
            system_prompt="You are Santos.",
            messages=[{"role": "user", "content": "hello"}],
            protected_content=["input_snapshot"],
        )
        assert req.system_prompt == "You are Santos."
        assert len(req.messages) == 1
        assert "input_snapshot" in req.protected_content

    def test_frozen(self):
        req = CompactionRequest()
        with pytest.raises(AttributeError):
            req.model = "different"


class TestCompactionResult:
    def test_defaults(self):
        result = CompactionResult()
        assert result.tokens_before == 0
        assert result.tokens_after == 0
        assert result.strategy_used == CompactionStrategy.ANTHROPIC_API

    def test_with_values(self):
        result = CompactionResult(
            compacted_messages=[{"role": "user", "content": "summary"}],
            tokens_before=10000,
            tokens_after=6000,
            strategy_used=CompactionStrategy.SESSION_BRIDGE,
            protected_fields_preserved=2,
        )
        assert result.tokens_before == 10000
        assert result.tokens_after == 6000
        assert result.protected_fields_preserved == 2


class TestCompactionClient:
    def test_default_config(self):
        client = CompactionClient()
        assert client.config.threshold == 0.8
        assert client.config.max_tokens == 128_000

    def test_needs_compaction_below_threshold(self):
        client = CompactionClient()
        assert client.needs_compaction(50_000) is False

    def test_needs_compaction_at_threshold(self):
        client = CompactionClient()
        assert client.needs_compaction(102_400) is True  # 80% of 128k

    def test_needs_compaction_above_threshold(self):
        client = CompactionClient()
        assert client.needs_compaction(120_000) is True

    def test_custom_threshold(self):
        config = CompactionConfig(threshold=0.5, max_tokens=100_000)
        client = CompactionClient(config)
        assert client.needs_compaction(50_000) is True
        assert client.needs_compaction(49_999) is False

    def test_build_request_basic(self):
        client = CompactionClient()
        req = client.build_request(
            system_prompt="system",
            messages=[{"role": "user", "content": "hi"}],
        )
        assert isinstance(req, CompactionRequest)
        assert req.system_prompt == "system"
        assert len(req.messages) == 1
        assert req.protected_content == []

    def test_build_request_with_protection(self):
        client = CompactionClient()
        req = client.build_request(
            system_prompt="system",
            messages=[],
            protected_content=["input_snapshot"],
        )
        assert "input_snapshot" in req.protected_content

    def test_build_request_merges_config_protected(self):
        config = CompactionConfig(protected_fields=["config_field"])
        client = CompactionClient(config)
        req = client.build_request(
            system_prompt="system",
            messages=[],
            protected_content=["call_field"],
        )
        assert "call_field" in req.protected_content
        assert "config_field" in req.protected_content

    def test_estimate_savings(self):
        client = CompactionClient()
        assert client.estimate_savings(10_000) == 4_000

    def test_estimate_savings_zero(self):
        client = CompactionClient()
        assert client.estimate_savings(0) == 0
