"""Deterministic broker queue alert policy; never reports tenant-level metrics."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from .rabbitmq_telemetry import QueueTelemetry


@dataclass(frozen=True, slots=True)
class BrokerAlert:
    code: str
    severity: str
    queue: str
    count: int


@dataclass(frozen=True, slots=True)
class BrokerThresholds:
    ready_warning: int = 100
    ready_critical: int = 1000
    unacked_warning: int = 100
    dlq_warning: int = 1

    def __post_init__(self):
        values = (self.ready_warning, self.ready_critical,
                  self.unacked_warning, self.dlq_warning)
        if any(isinstance(n, bool) or not isinstance(n, int)
               or n < 1 or n > 10_000_000 for n in values):
            raise ValueError("Positive bounded thresholds required")
        if self.ready_critical <= self.ready_warning:
            raise ValueError("Critical backlog threshold must exceed warning")


def evaluate_broker_alerts(queues: tuple[QueueTelemetry, ...],
                           thresholds: BrokerThresholds = BrokerThresholds()) -> list[dict]:
    alerts = []
    for queue in queues:
        if queue.is_dlq:
            if queue.total >= thresholds.dlq_warning:
                alerts.append(BrokerAlert("DLQ_NONEMPTY", "critical",
                                          queue.name, queue.total))
            continue
        if queue.ready >= thresholds.ready_critical:
            alerts.append(BrokerAlert("QUEUE_BACKLOG_CRITICAL", "critical",
                                      queue.name, queue.ready))
        elif queue.ready >= thresholds.ready_warning:
            alerts.append(BrokerAlert("QUEUE_BACKLOG", "warning",
                                      queue.name, queue.ready))
        if queue.unacked >= thresholds.unacked_warning:
            alerts.append(BrokerAlert("QUEUE_UNACKED", "warning",
                                      queue.name, queue.unacked))
        if queue.ready > 0 and queue.consumers == 0:
            alerts.append(BrokerAlert("QUEUE_NO_CONSUMER", "critical",
                                      queue.name, queue.ready))
    return [asdict(alert) for alert in alerts]
