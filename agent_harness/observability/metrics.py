"""Metrics types for operativo monitoring.

Defines metric types and collectors. No external dependencies.
Actual metrics backends (Prometheus, CloudWatch) plug in via protocol.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum


class MetricType(StrEnum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass(frozen=True)
class MetricPoint:
    """A single metric data point."""
    name: str
    value: float
    metric_type: MetricType
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = 0.0


class MetricsCollector:
    """Collects metric points for an operativo.

    Usage:
        collector = MetricsCollector(operativo_id="op-1")
        collector.increment("phase_transitions", labels={"phase": "1"})
        collector.gauge("context_tokens", 50000)
        collector.observe("phase_duration_seconds", 12.5, labels={"agent": "santos"})
    """

    def __init__(self, operativo_id: str = "") -> None:
        self.operativo_id = operativo_id
        self._points: list[MetricPoint] = []

    def increment(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        self._points.append(MetricPoint(
            name=name, value=value, metric_type=MetricType.COUNTER,
            labels={"operativo_id": self.operativo_id, **(labels or {})},
            timestamp=time.time(),
        ))

    def gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        self._points.append(MetricPoint(
            name=name, value=value, metric_type=MetricType.GAUGE,
            labels={"operativo_id": self.operativo_id, **(labels or {})},
            timestamp=time.time(),
        ))

    def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        self._points.append(MetricPoint(
            name=name, value=value, metric_type=MetricType.HISTOGRAM,
            labels={"operativo_id": self.operativo_id, **(labels or {})},
            timestamp=time.time(),
        ))

    @property
    def points(self) -> list[MetricPoint]:
        return list(self._points)

    def points_by_name(self, name: str) -> list[MetricPoint]:
        return [p for p in self._points if p.name == name]
