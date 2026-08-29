from datetime import datetime, timezone

import pytest

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.workflow.in_memory_unit_of_work import (
    InMemoryWorkflowUnitOfWork,
)
from rkjo_kernel.workflow.outbox import OutboxMessage
from rkjo_kernel.workflow.outbox_publisher import (
    OutboxPublisher,
)


class RecordingEventBus:
    def __init__(self):
        self.published = []

    def publish_agent_message(
        self,
        *,
        queue_name,
        message,
    ):
        self.published.append(
            (queue_name, message)
        )


class FailingEventBus:
    def publish_agent_message(
        self,
        *,
        queue_name,
        message,
    ):
        raise RuntimeError("broker unavailable")


def make_outbox_message(
    *,
    outbox_id="outbox-001",
    queue_name="education.diagnostic",
):
    return OutboxMessage(
        outbox_id=outbox_id,
        queue_name=queue_name,
        message=AgentMessage(
            source="rkjo.workflow",
            target="diagnostic.agent",
            message_type="workflow.step.execute",
            correlation_id="corr-001",
            payload={
                "student_id": "student-001",
            },
        ),
        created_at=datetime.now(timezone.utc),
    )


def test_publish_pending_publishes_and_marks_message():
    uow = InMemoryWorkflowUnitOfWork()
    message = make_outbox_message()

    with uow:
        uow.outbox.add(message)
        uow.commit()

    event_bus = RecordingEventBus()

    publisher = OutboxPublisher(
        event_bus=event_bus,
        uow_factory=lambda: uow,
    )

    published_count = publisher.publish_pending()

    assert published_count == 1
    assert len(event_bus.published) == 1

    queue_name, published_message = (
        event_bus.published[0]
    )

    assert queue_name == "education.diagnostic"
    assert (
        published_message.message_id
        == message.message.message_id
    )

    with uow:
        assert uow.outbox.pending() == []


def test_publish_pending_returns_zero_when_outbox_empty():
    uow = InMemoryWorkflowUnitOfWork()
    event_bus = RecordingEventBus()

    publisher = OutboxPublisher(
        event_bus=event_bus,
        uow_factory=lambda: uow,
    )

    published_count = publisher.publish_pending()

    assert published_count == 0
    assert event_bus.published == []


def test_publish_failure_leaves_message_pending():
    uow = InMemoryWorkflowUnitOfWork()
    message = make_outbox_message()

    with uow:
        uow.outbox.add(message)
        uow.commit()

    publisher = OutboxPublisher(
        event_bus=FailingEventBus(),
        uow_factory=lambda: uow,
    )

    with pytest.raises(
        RuntimeError,
        match="broker unavailable",
    ):
        publisher.publish_pending()

    with uow:
        pending = uow.outbox.pending()

    assert len(pending) == 1
    assert pending[0].outbox_id == "outbox-001"


def test_publish_pending_respects_limit():
    uow = InMemoryWorkflowUnitOfWork()

    with uow:
        uow.outbox.add(
            make_outbox_message(
                outbox_id="outbox-001",
            )
        )
        uow.outbox.add(
            make_outbox_message(
                outbox_id="outbox-002",
            )
        )
        uow.outbox.add(
            make_outbox_message(
                outbox_id="outbox-003",
            )
        )
        uow.commit()

    event_bus = RecordingEventBus()

    publisher = OutboxPublisher(
        event_bus=event_bus,
        uow_factory=lambda: uow,
    )

    published_count = publisher.publish_pending(
        limit=2,
    )

    assert published_count == 2
    assert len(event_bus.published) == 2

    with uow:
        pending = uow.outbox.pending()

    assert len(pending) == 1
    assert pending[0].outbox_id == "outbox-003"


def test_publish_pending_rejects_invalid_limit():
    uow = InMemoryWorkflowUnitOfWork()

    publisher = OutboxPublisher(
        event_bus=RecordingEventBus(),
        uow_factory=lambda: uow,
    )

    with pytest.raises(
        ValueError,
        match="limit must be greater than zero",
    ):
        publisher.publish_pending(
            limit=0,
        )
