"""Heartbeat monitor — Temporal cron workflow for operativo health.

Runs every 30 minutes. No LLM calls — pure metadata monitoring.
Checks:
- Stuck operativos (no phase transition in 15+ minutes)
- Resource exhaustion (context window approaching limits)
- Cache hit rate drops below 60%
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class HealthAlert:
    """A single health alert from the heartbeat monitor."""
    operativo_id: str
    alert_type: str
    severity: AlertSeverity
    message: str
    timestamp: str


@dataclass(frozen=True)
class HeartbeatConfig:
    """Configuration for the heartbeat monitor."""
    stuck_threshold_minutes: int = 15
    context_warning_threshold: float = 0.7
    context_critical_threshold: float = 0.9
    cache_hit_rate_minimum: float = 0.6
    cron_interval_minutes: int = 30


@dataclass
class HeartbeatResult:
    """Result of a heartbeat check cycle."""
    checked_at: str = ""
    operativos_checked: int = 0
    alerts: list[HealthAlert] = field(default_factory=list)

    @property
    def has_critical(self) -> bool:
        return any(a.severity == AlertSeverity.CRITICAL for a in self.alerts)

    @property
    def alert_count(self) -> int:
        return len(self.alerts)


def check_stuck(
    operativo_id: str,
    last_phase_transition: datetime,
    now: datetime,
    threshold_minutes: int = 15,
) -> HealthAlert | None:
    """Check if an operativo is stuck (no phase transition in threshold minutes)."""
    elapsed = now - last_phase_transition
    if elapsed > timedelta(minutes=threshold_minutes):
        return HealthAlert(
            operativo_id=operativo_id,
            alert_type="stuck_operativo",
            severity=AlertSeverity.WARNING,
            message=f"No phase transition in {int(elapsed.total_seconds() / 60)} minutes",
            timestamp=now.isoformat(),
        )
    return None


def check_context_usage(
    operativo_id: str,
    current_tokens: int,
    max_tokens: int,
    warning_threshold: float = 0.7,
    critical_threshold: float = 0.9,
) -> HealthAlert | None:
    """Check if context window usage is approaching limits."""
    usage = current_tokens / max_tokens if max_tokens > 0 else 0
    if usage >= critical_threshold:
        return HealthAlert(
            operativo_id=operativo_id,
            alert_type="context_exhaustion",
            severity=AlertSeverity.CRITICAL,
            message=f"Context usage at {usage:.0%} ({current_tokens}/{max_tokens} tokens)",
            timestamp=datetime.now().isoformat(),
        )
    if usage >= warning_threshold:
        return HealthAlert(
            operativo_id=operativo_id,
            alert_type="context_warning",
            severity=AlertSeverity.WARNING,
            message=f"Context usage at {usage:.0%} ({current_tokens}/{max_tokens} tokens)",
            timestamp=datetime.now().isoformat(),
        )
    return None


def check_cache_hit_rate(
    operativo_id: str,
    hit_rate: float,
    minimum: float = 0.6,
) -> HealthAlert | None:
    """Check if cache hit rate has dropped below minimum."""
    if hit_rate < minimum:
        return HealthAlert(
            operativo_id=operativo_id,
            alert_type="low_cache_hit_rate",
            severity=AlertSeverity.WARNING,
            message=f"Cache hit rate {hit_rate:.0%} below minimum {minimum:.0%}",
            timestamp=datetime.now().isoformat(),
        )
    return None
