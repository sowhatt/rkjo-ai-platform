"""Tenant-scoped teacher alert routing; independent of learning evidence.

In-memory sink is only a reference implementation for tests. Production
requires durable outbox, broker retries, access checks and streaming transport.
"""
from dataclasses import dataclass, field
from uuid import UUID

from rkjo_education.supervision.safety_alerts import SafetyAlert


class AlertTenantMismatch(PermissionError):
    pass


@dataclass
class InMemoryTeacherAlertSink:
    tenant_id: UUID
    delivered: list[SafetyAlert] = field(default_factory=list)
    seen_ids: set[UUID] = field(default_factory=set)

    def publish(self, alert: SafetyAlert) -> None:
        if alert.tenant_id != self.tenant_id:
            raise AlertTenantMismatch("Alert tenant does not match teacher queue tenant")
        if alert.alert_id in self.seen_ids:
            return
        self.seen_ids.add(alert.alert_id)
        self.delivered.append(alert)


def visible_alerts(sink: InMemoryTeacherAlertSink, *, viewer_tenant_id: UUID) -> tuple[SafetyAlert, ...]:
    if viewer_tenant_id != sink.tenant_id:
        raise AlertTenantMismatch("Viewer cannot inspect alerts from another tenant")
    return tuple(sink.delivered)
