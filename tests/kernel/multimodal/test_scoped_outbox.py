"""Queue isolation tests for the shared RKJO workflow outbox."""
from datetime import datetime, timezone

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.workflow.in_memory_unit_of_work import InMemoryWorkflowUnitOfWork
from rkjo_kernel.workflow.outbox import OutboxMessage
from rkjo_kernel.workflow.outbox_publisher import OutboxPublisher


class Bus:
    def __init__(self):
        self.sent = []

    def publish_agent_message(self, queue_name, message):
        self.sent.append((queue_name, message.message_id))


def test_scoped_publisher_leaves_unrelated_workflow_events_untouched():
    uow = InMemoryWorkflowUnitOfWork()
    with uow as unit:
        for name in ("production.queue", "test.queue"):
            message = AgentMessage(source="test", target="test", payload={})
            unit.outbox.add(OutboxMessage(
                outbox_id=message.message_id, queue_name=name,
                message=message, created_at=datetime.now(timezone.utc),
            ))
        unit.commit()
    bus = Bus()
    publisher = OutboxPublisher(
        event_bus=bus, uow_factory=lambda: uow, queue_name="test.queue",
    )
    assert publisher.publish_pending(limit=10) == 1
    assert len(bus.sent) == 1
    assert bus.sent[0][0] == "test.queue"
    assert len(uow.outbox.pending(queue_name="production.queue")) == 1
    assert uow.outbox.pending(queue_name="test.queue") == []


def test_default_publisher_still_processes_all_queues():
    uow = InMemoryWorkflowUnitOfWork()
    with uow as unit:
        for name in ("q1", "q2"):
            message = AgentMessage(source="test", target="test", payload={})
            unit.outbox.add(OutboxMessage(
                outbox_id=message.message_id, queue_name=name,
                message=message, created_at=datetime.now(timezone.utc),
            ))
        unit.commit()
    bus = Bus()
    assert OutboxPublisher(event_bus=bus, uow_factory=lambda: uow).publish_pending(limit=5) == 2
    assert {q for q, _ in bus.sent} == {"q1", "q2"}
