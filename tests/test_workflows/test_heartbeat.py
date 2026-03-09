"""Tests for heartbeat monitor."""

import pytest
from datetime import datetime, timedelta

from agent_harness.workflows.heartbeat import (
    AlertSeverity,
    HealthAlert,
    HeartbeatConfig,
    HeartbeatResult,
    check_stuck,
    check_context_usage,
    check_cache_hit_rate,
)


class TestHealthAlert:
    def test_creation(self):
        alert = HealthAlert(
            operativo_id="op-1",
            alert_type="stuck",
            severity=AlertSeverity.WARNING,
            message="Stuck for 20 minutes",
            timestamp="2026-02-21T12:00:00",
        )
        assert alert.operativo_id == "op-1"
        assert alert.severity == AlertSeverity.WARNING

    def test_frozen(self):
        alert = HealthAlert(
            operativo_id="op-1", alert_type="x",
            severity=AlertSeverity.INFO, message="y",
            timestamp="z",
        )
        with pytest.raises(AttributeError):
            alert.message = "changed"


class TestHeartbeatConfig:
    def test_defaults(self):
        config = HeartbeatConfig()
        assert config.stuck_threshold_minutes == 15
        assert config.context_warning_threshold == 0.7
        assert config.context_critical_threshold == 0.9
        assert config.cache_hit_rate_minimum == 0.6
        assert config.cron_interval_minutes == 30

    def test_custom(self):
        config = HeartbeatConfig(stuck_threshold_minutes=30, cron_interval_minutes=60)
        assert config.stuck_threshold_minutes == 30


class TestHeartbeatResult:
    def test_empty(self):
        result = HeartbeatResult()
        assert result.operativos_checked == 0
        assert result.alerts == []
        assert result.has_critical is False
        assert result.alert_count == 0

    def test_with_alerts(self):
        alert = HealthAlert(
            operativo_id="op-1", alert_type="stuck",
            severity=AlertSeverity.CRITICAL, message="stuck",
            timestamp="now",
        )
        result = HeartbeatResult(
            checked_at="now", operativos_checked=5, alerts=[alert],
        )
        assert result.has_critical is True
        assert result.alert_count == 1

    def test_no_critical_with_warnings_only(self):
        alert = HealthAlert(
            operativo_id="op-1", alert_type="warn",
            severity=AlertSeverity.WARNING, message="warn",
            timestamp="now",
        )
        result = HeartbeatResult(alerts=[alert])
        assert result.has_critical is False
        assert result.alert_count == 1


class TestCheckStuck:
    def test_not_stuck(self):
        now = datetime(2026, 2, 21, 12, 0)
        last = now - timedelta(minutes=10)
        assert check_stuck("op-1", last, now) is None

    def test_stuck(self):
        now = datetime(2026, 2, 21, 12, 0)
        last = now - timedelta(minutes=20)
        alert = check_stuck("op-1", last, now)
        assert alert is not None
        assert alert.alert_type == "stuck_operativo"
        assert alert.severity == AlertSeverity.WARNING
        assert "20 minutes" in alert.message

    def test_exactly_at_threshold(self):
        now = datetime(2026, 2, 21, 12, 0)
        last = now - timedelta(minutes=15)
        assert check_stuck("op-1", last, now) is None  # > not >=

    def test_custom_threshold(self):
        now = datetime(2026, 2, 21, 12, 0)
        last = now - timedelta(minutes=35)
        alert = check_stuck("op-1", last, now, threshold_minutes=30)
        assert alert is not None


class TestCheckContextUsage:
    def test_below_warning(self):
        assert check_context_usage("op-1", 50_000, 128_000) is None

    def test_at_warning(self):
        alert = check_context_usage("op-1", 90_000, 128_000)
        assert alert is not None
        assert alert.severity == AlertSeverity.WARNING
        assert alert.alert_type == "context_warning"

    def test_at_critical(self):
        alert = check_context_usage("op-1", 120_000, 128_000)
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.alert_type == "context_exhaustion"

    def test_zero_max_tokens(self):
        assert check_context_usage("op-1", 100, 0) is None

    def test_custom_thresholds(self):
        alert = check_context_usage(
            "op-1", 60_000, 100_000,
            warning_threshold=0.5, critical_threshold=0.8,
        )
        assert alert is not None
        assert alert.severity == AlertSeverity.WARNING


class TestCheckCacheHitRate:
    def test_good_rate(self):
        assert check_cache_hit_rate("op-1", 0.8) is None

    def test_low_rate(self):
        alert = check_cache_hit_rate("op-1", 0.5)
        assert alert is not None
        assert alert.alert_type == "low_cache_hit_rate"
        assert alert.severity == AlertSeverity.WARNING

    def test_at_minimum(self):
        assert check_cache_hit_rate("op-1", 0.6) is None  # >= minimum is ok

    def test_custom_minimum(self):
        alert = check_cache_hit_rate("op-1", 0.7, minimum=0.8)
        assert alert is not None
