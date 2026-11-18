"""OMNI-016.4.3.3: deterministic RabbitMQ alert thresholds."""
import pytest

from rkjo_kernel.omnichannel.rabbitmq_alerts import (
    BrokerThresholds, evaluate_broker_alerts,
)
from rkjo_kernel.omnichannel.rabbitmq_telemetry import QueueTelemetry


def queue(*, ready=0, unacked=0, consumers=1, dlq=False):
    return QueueTelemetry(
        name="agent.dlq" if dlq else "agent",
        ready=ready, unacked=unacked, consumers=consumers,
        total=ready + unacked, is_dlq=dlq,
    )


def test_no_alerts_on_empty_or_healthy_queue():
    assert evaluate_broker_alerts((queue(), queue(consumers=0))) == []


def test_dlq_is_critical_even_when_no_consumer():
    alerts = evaluate_broker_alerts((queue(ready=1,consumers=0,dlq=True),))
    assert alerts == [{
        "code":"DLQ_NONEMPTY", "severity":"critical",
        "queue":"agent.dlq", "count":1,
    }]


def test_backlog_and_no_consumers_are_distinct():
    codes = {a["code"] for a in evaluate_broker_alerts((
        queue(ready=100,consumers=0),
    ))}
    assert codes == {"QUEUE_BACKLOG", "QUEUE_NO_CONSUMER"}


def test_critical_backlog_and_unacked_threshold():
    codes = {a["code"] for a in evaluate_broker_alerts((
        queue(ready=1000,unacked=100),
    ))}
    assert codes == {"QUEUE_BACKLOG_CRITICAL", "QUEUE_UNACKED"}


@pytest.mark.parametrize("thresholds", [
    dict(ready_warning=0),
    dict(ready_warning=100, ready_critical=100),
    dict(dlq_warning=-1),
    dict(unacked_warning=True),
])
def test_invalid_thresholds_fail_closed(thresholds):
    with pytest.raises(ValueError):
        BrokerThresholds(**thresholds)
