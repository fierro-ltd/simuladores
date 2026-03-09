"""Tests for metrics types."""

import pytest

from agent_harness.observability.metrics import (
    MetricType,
    MetricPoint,
    MetricsCollector,
)


class TestMetricPoint:
    def test_creation(self):
        point = MetricPoint(
            name="phase_duration", value=12.5,
            metric_type=MetricType.HISTOGRAM,
        )
        assert point.name == "phase_duration"
        assert point.value == 12.5

    def test_with_labels(self):
        point = MetricPoint(
            name="counter", value=1,
            metric_type=MetricType.COUNTER,
            labels={"agent": "santos"},
        )
        assert point.labels["agent"] == "santos"

    def test_frozen(self):
        point = MetricPoint(name="x", value=0, metric_type=MetricType.GAUGE)
        with pytest.raises(AttributeError):
            point.value = 1


class TestMetricsCollector:
    def test_increment(self):
        collector = MetricsCollector(operativo_id="op-1")
        collector.increment("phase_transitions")
        assert len(collector.points) == 1
        assert collector.points[0].metric_type == MetricType.COUNTER
        assert collector.points[0].value == 1.0

    def test_increment_custom_value(self):
        collector = MetricsCollector()
        collector.increment("api_calls", value=3)
        assert collector.points[0].value == 3

    def test_gauge(self):
        collector = MetricsCollector(operativo_id="op-1")
        collector.gauge("context_tokens", 50000)
        assert collector.points[0].metric_type == MetricType.GAUGE
        assert collector.points[0].value == 50000

    def test_observe(self):
        collector = MetricsCollector()
        collector.observe("phase_duration_seconds", 12.5, labels={"agent": "santos"})
        point = collector.points[0]
        assert point.metric_type == MetricType.HISTOGRAM
        assert point.labels["agent"] == "santos"

    def test_operativo_id_in_labels(self):
        collector = MetricsCollector(operativo_id="op-1")
        collector.increment("x")
        assert collector.points[0].labels["operativo_id"] == "op-1"

    def test_multiple_points(self):
        collector = MetricsCollector()
        collector.increment("a")
        collector.gauge("b", 10)
        collector.observe("c", 5.5)
        assert len(collector.points) == 3

    def test_points_by_name(self):
        collector = MetricsCollector()
        collector.increment("x")
        collector.increment("y")
        collector.increment("x")
        assert len(collector.points_by_name("x")) == 2

    def test_points_returns_copy(self):
        collector = MetricsCollector()
        collector.increment("x")
        points = collector.points
        points.clear()
        assert len(collector.points) == 1
