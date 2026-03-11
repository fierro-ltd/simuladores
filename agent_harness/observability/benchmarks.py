"""Performance benchmark types for operativo profiling.

Defines benchmark harness types for measuring phase durations,
token usage, and end-to-end operativo performance.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PhaseBenchmark:
    """Benchmark result for a single phase."""
    phase: int
    agent: str
    duration_seconds: float
    tokens_used: int = 0
    cache_hit: bool = False


@dataclass
class OperativoBenchmark:
    """Benchmark result for a full operativo lifecycle."""
    operativo_id: str
    domain: str
    phases: list[PhaseBenchmark] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def total_duration(self) -> float:
        if self.end_time > self.start_time:
            return self.end_time - self.start_time
        return sum(p.duration_seconds for p in self.phases)

    @property
    def total_tokens(self) -> int:
        return sum(p.tokens_used for p in self.phases)

    @property
    def cache_hit_rate(self) -> float:
        if not self.phases:
            return 0.0
        hits = sum(1 for p in self.phases if p.cache_hit)
        return hits / len(self.phases)


@dataclass(frozen=True)
class BenchmarkTargets:
    """Performance targets for operativo phases (seconds)."""
    plan_max: float = 15.0
    investigate_max: float = 20.0
    execute_max: float = 60.0
    qa_max: float = 30.0
    synthesize_max: float = 10.0
    post_job_max: float = 5.0
    total_max: float = 120.0


def check_targets(
    benchmark: OperativoBenchmark,
    targets: BenchmarkTargets | None = None,
) -> list[str]:
    """Check benchmark against targets. Returns list of violations."""
    t = targets or BenchmarkTargets()
    violations: list[str] = []

    phase_limits = {
        1: ("plan", t.plan_max),
        2: ("investigate", t.investigate_max),
        3: ("execute", t.execute_max),
        4: ("qa", t.qa_max),
        5: ("synthesize", t.synthesize_max),
        6: ("post_job", t.post_job_max),
    }

    for phase_bench in benchmark.phases:
        if phase_bench.phase in phase_limits:
            name, limit = phase_limits[phase_bench.phase]
            if phase_bench.duration_seconds > limit:
                violations.append(
                    f"Phase {phase_bench.phase} ({name}): "
                    f"{phase_bench.duration_seconds:.1f}s > {limit:.1f}s"
                )

    if benchmark.total_duration > t.total_max:
        violations.append(
            f"Total: {benchmark.total_duration:.1f}s > {t.total_max:.1f}s"
        )

    return violations
