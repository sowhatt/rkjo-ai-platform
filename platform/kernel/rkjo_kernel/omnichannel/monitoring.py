"""OMNI-016.3 — tenant-scoped Omnichannel operational alert evaluation.

Read-only and deterministic: derives warnings from existing trusted
PostgreSQL operational counters. No message content, PII, credentials or
raw webhook payloads appear in alert output. Publishing alerts to a
notification service is a separate, explicit integration.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from rkjo_kernel.omnichannel.operations import OperationalSnapshot, PostgreSQLOmnichannelOperations


class AlertSeverity(str, Enum):
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class AlertThresholds:
    inbound_backlog: int = 100
    route_backlog: int = 100
    outbound_backlog: int = 50
    # A failed, uncertain, or unbound provider operation is never acceptable.
    def __post_init__(self):
        if any(not isinstance(v, int) or isinstance(v, bool) or v < 1 for v in (
            self.inbound_backlog, self.route_backlog, self.outbound_backlog
        )):
            raise ValueError("Backlog thresholds must be positive integers.")


@dataclass(frozen=True, slots=True)
class OmnichannelAlert:
    tenant_id: str
    code: str
    severity: AlertSeverity
    count: int
    message: str

    @property
    def dedup_key(self) -> str:
        return f"omnichannel:{self.tenant_id}:{self.code}"


@dataclass(frozen=True, slots=True)
class OmnichannelMonitoringReport:
    tenant_id: str
    evaluated_at: datetime
    alerts: tuple[OmnichannelAlert, ...]

    @property
    def healthy(self) -> bool:
        return not self.alerts

    @property
    def has_critical(self) -> bool:
        return any(alert.severity == AlertSeverity.CRITICAL for alert in self.alerts)


_CHECKS = (
    ("INBOUND_BACKLOG", "inbound", "pending", AlertSeverity.WARNING, "Inbound queue backlog"),
    ("ROUTE_BACKLOG", "routes", "pending", AlertSeverity.WARNING, "Routing outbox backlog"),
    ("OUTBOUND_BACKLOG", "outbound", "pending", AlertSeverity.WARNING, "Outbound delivery backlog"),
    ("INBOUND_FAILED", "inbound", "failed", AlertSeverity.CRITICAL, "Failed inbound events"),
    ("ROUTE_FAILED", "routes", "failed", AlertSeverity.CRITICAL, "Failed routing events"),
    ("OUTBOUND_FAILED", "outbound", "failed", AlertSeverity.CRITICAL, "Failed outbound deliveries"),
    ("INBOUND_EXPIRED_LEASE", "inbound", "expired_leases", AlertSeverity.CRITICAL, "Expired inbound leases"),
    ("ROUTE_EXPIRED_LEASE", "routes", "expired_leases", AlertSeverity.CRITICAL, "Expired routing leases"),
    ("OUTBOUND_EXPIRED_LEASE", "outbound", "expired_leases", AlertSeverity.CRITICAL, "Expired outbound leases"),
)


def evaluate_snapshot(
    snapshot: OperationalSnapshot, *,
    thresholds: AlertThresholds | None = None,
    now: datetime | None = None,
) -> OmnichannelMonitoringReport:
    thresholds = thresholds or AlertThresholds()
    now = now or datetime.now(timezone.utc)
    if not snapshot.tenant_id.strip() or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Valid tenant and timezone-aware evaluation time required.")
    limits = {
        "INBOUND_BACKLOG": thresholds.inbound_backlog,
        "ROUTE_BACKLOG": thresholds.route_backlog,
        "OUTBOUND_BACKLOG": thresholds.outbound_backlog,
    }
    alerts: list[OmnichannelAlert] = []
    for code, queue_name, field, severity, label in _CHECKS:
        count = getattr(getattr(snapshot, queue_name), field)
        if count >= limits.get(code, 1):
            alerts.append(OmnichannelAlert(snapshot.tenant_id, code, severity, count, label))
    for code, count, label in (
        ("UNCERTAIN_OUTBOUND", snapshot.uncertain_outbound,
         "Uncertain provider acceptance: reconciliation required"),
        ("PROVIDER_CONFIRMED_UNCOMMITTED", snapshot.provider_confirmed_uncommitted,
         "Provider acceptance not finalized in notification store"),
        ("SENT_WITHOUT_BINDING", snapshot.sent_without_binding,
         "Sent notification without matching provider proof"),
    ):
        if count:
            alerts.append(OmnichannelAlert(
                snapshot.tenant_id, code, AlertSeverity.CRITICAL, count, label
            ))
    return OmnichannelMonitoringReport(snapshot.tenant_id, now, tuple(alerts))


class PostgreSQLOmnichannelMonitor:
    def __init__(self, *, operations: PostgreSQLOmnichannelOperations,
                 thresholds: AlertThresholds | None = None):
        self.operations = operations
        self.thresholds = thresholds or AlertThresholds()

    def check(self, *, tenant_id: str, now: datetime | None = None) -> OmnichannelMonitoringReport:
        now = now or datetime.now(timezone.utc)
        return evaluate_snapshot(
            self.operations.snapshot(tenant_id=tenant_id, now=now),
            thresholds=self.thresholds, now=now,
        )
