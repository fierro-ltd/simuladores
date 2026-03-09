"""Tests for performance benchmark types."""

import pytest

from agent_harness.observability.benchmarks import (
    PhaseBenchmark,
    OperativoBenchmark,
    BenchmarkTargets,
    check_targets,
)


class TestPhaseBenchmark:
    def test_creation(self):
        bench = PhaseBenchmark(phase=1, agent="santos", duration_seconds=5.0)
        assert bench.phase == 1
        assert bench.duration_seconds == 5.0

    def test_with_tokens(self):
        bench = PhaseBenchmark(
            phase=3, agent="lamponne",
            duration_seconds=30.0, tokens_used=15000, cache_hit=True,
        )
        assert bench.tokens_used == 15000
        assert bench.cache_hit is True

    def test_frozen(self):
        bench = PhaseBenchmark(phase=1, agent="x", duration_seconds=1.0)
        with pytest.raises(AttributeError):
            bench.duration_seconds = 2.0


class TestOperativoBenchmark:
    def test_empty(self):
        bench = OperativoBenchmark(operativo_id="op-1", domain="dce")
        assert bench.total_duration == 0
        assert bench.total_tokens == 0
        assert bench.cache_hit_rate == 0.0

    def test_total_duration_from_phases(self):
        bench = OperativoBenchmark(
            operativo_id="op-1", domain="dce",
            phases=[
                PhaseBenchmark(phase=1, agent="santos", duration_seconds=5.0),
                PhaseBenchmark(phase=3, agent="lamponne", duration_seconds=30.0),
            ],
        )
        assert bench.total_duration == 35.0

    def test_total_duration_from_times(self):
        bench = OperativoBenchmark(
            operativo_id="op-1", domain="dce",
            start_time=100.0, end_time=145.0,
        )
        assert bench.total_duration == 45.0

    def test_total_tokens(self):
        bench = OperativoBenchmark(
            operativo_id="op-1", domain="dce",
            phases=[
                PhaseBenchmark(phase=1, agent="santos", duration_seconds=5.0, tokens_used=5000),
                PhaseBenchmark(phase=3, agent="lamponne", duration_seconds=30.0, tokens_used=15000),
            ],
        )
        assert bench.total_tokens == 20000

    def test_cache_hit_rate(self):
        bench = OperativoBenchmark(
            operativo_id="op-1", domain="dce",
            phases=[
                PhaseBenchmark(phase=1, agent="santos", duration_seconds=5.0, cache_hit=True),
                PhaseBenchmark(phase=2, agent="medina", duration_seconds=10.0, cache_hit=False),
                PhaseBenchmark(phase=3, agent="lamponne", duration_seconds=30.0, cache_hit=True),
            ],
        )
        assert abs(bench.cache_hit_rate - 2/3) < 0.01


class TestBenchmarkTargets:
    def test_defaults(self):
        targets = BenchmarkTargets()
        assert targets.plan_max == 15.0
        assert targets.total_max == 120.0

    def test_custom(self):
        targets = BenchmarkTargets(plan_max=30.0, total_max=300.0)
        assert targets.plan_max == 30.0


class TestCheckTargets:
    def test_no_violations(self):
        bench = OperativoBenchmark(
            operativo_id="op-1", domain="dce",
            phases=[
                PhaseBenchmark(phase=1, agent="santos", duration_seconds=10.0),
                PhaseBenchmark(phase=3, agent="lamponne", duration_seconds=50.0),
            ],
        )
        assert check_targets(bench) == []

    def test_phase_violation(self):
        bench = OperativoBenchmark(
            operativo_id="op-1", domain="dce",
            phases=[
                PhaseBenchmark(phase=1, agent="santos", duration_seconds=20.0),
            ],
        )
        violations = check_targets(bench)
        assert len(violations) == 1
        assert "Phase 1" in violations[0]

    def test_total_violation(self):
        bench = OperativoBenchmark(
            operativo_id="op-1", domain="dce",
            start_time=0, end_time=200,
            phases=[],
        )
        violations = check_targets(bench)
        assert any("Total" in v for v in violations)

    def test_custom_targets(self):
        bench = OperativoBenchmark(
            operativo_id="op-1", domain="dce",
            phases=[
                PhaseBenchmark(phase=1, agent="santos", duration_seconds=5.0),
            ],
        )
        targets = BenchmarkTargets(plan_max=3.0)
        violations = check_targets(bench, targets)
        assert len(violations) == 1
