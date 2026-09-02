from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pika
import pytest

from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.workflow.in_memory_unit_of_work import (
    InMemoryWorkflowUnitOfWork,
)
from rkjo_kernel.workflow.outbox import OutboxMessage
from rkjo_kernel.workflow.outbox_publisher import OutboxPublisher


def make_agent_message() -> AgentMessage:
    return AgentMessage(
        message_id="confirm-message-001",
        correlation_id="confirm-correlation-001",
        source="rkjo.workflow",
        target="diagnostic.agent",
        message_type="workflow.step.execute",
        payload={"student_id": "student-001"},
    )


def make_outbox_message() -> OutboxMessage:
    return OutboxMessage(
        outbox_id="outbox-confirm-001",
        queue_name="education.diagnostic",
        message=make_agent_message(),
        created_at=datetime.now(timezone.utc),
    )


def test_rabbitmq_bus_enables_publisher_confirms_on_channel():
    channel = Mock()
    connection = Mock()
    connection.channel.return_value = channel

    with patch(
        "rkjo_kernel.events.rabbitmq_event_bus.pika.BlockingConnection",
        return_value=connection,
    ):
        RabbitMQEventBus()

    channel.confirm_delivery.assert_called_once_with()


def test_agent_publish_is_mandatory_after_confirm_mode_enabled():
    bus = RabbitMQEventBus.__new__(RabbitMQEventBus)
    bus.channel = Mock()
    bus.logger = Mock()

    message = make_agent_message()

    bus.publish_agent_message(
        queue_name="education.diagnostic",
        message=message,
    )

    bus.channel.queue_declare.assert_called_once_with(
        queue="education.diagnostic",
        durable=True,
    )

    call = bus.channel.basic_publish.call_args
    assert call.kwargs["exchange"] == ""
    assert call.kwargs["routing_key"] == "education.diagnostic"
    assert call.kwargs["mandatory"] is True
    assert call.kwargs["properties"].delivery_mode == (
        pika.DeliveryMode.Persistent.value
    )


def test_outbox_stays_pending_when_rabbitmq_nacks_publish():
    uow = InMemoryWorkflowUnitOfWork()
    outbox_message = make_outbox_message()

    with uow:
        uow.outbox.add(outbox_message)
        uow.commit()

    bus = RabbitMQEventBus.__new__(RabbitMQEventBus)
    bus.channel = Mock()
    bus.logger = Mock()
    bus.channel.basic_publish.side_effect = pika.exceptions.NackError([])

    publisher = OutboxPublisher(
        event_bus=bus,
        uow_factory=lambda: uow,
    )

    with pytest.raises(pika.exceptions.NackError):
        publisher.publish_pending()

    with uow:
        pending = uow.outbox.pending()

    assert len(pending) == 1
    assert pending[0].outbox_id == "outbox-confirm-001"


def test_outbox_is_marked_published_only_after_confirmed_publish():
    uow = InMemoryWorkflowUnitOfWork()
    outbox_message = make_outbox_message()

    with uow:
        uow.outbox.add(outbox_message)
        uow.commit()

    bus = RabbitMQEventBus.__new__(RabbitMQEventBus)
    bus.channel = Mock()
    bus.logger = Mock()

    publisher = OutboxPublisher(
        event_bus=bus,
        uow_factory=lambda: uow,
    )

    published_count = publisher.publish_pending()

    assert published_count == 1
    bus.channel.basic_publish.assert_called_once()

    with uow:
        assert uow.outbox.pending() == []
