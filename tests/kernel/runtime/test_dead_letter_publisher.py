import pytest

from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.runtime.dead_letter_publisher import (
    DeadLetterPublisher,
)


class FakeEventBus(EventBus):
    def __init__(self):
        self.messages = []

    def publish(self, queue_name, message):
        pass

    def consume(self, queue_name, callback):
        pass

    def publish_agent_message(
        self,
        queue_name,
        message,
    ):
        self.messages.append(
            (queue_name, message)
        )

    def consume_agent_messages(
        self,
        queue_name,
        callback,
    ):
        pass

    def close(self):
        pass


def make_message():
    return AgentMessage(
        message_id="original-001",
        correlation_id="corr-001",
        source="rkjo.workflow",
        target="weather.agent",
        message_type="workflow.step.execute",
        payload={
            "parcel_id": "P-100"
        },
        metadata={
            "workflow_execution_id": "exec-001",
            "workflow_step_id": "weather",
            "attempt": 3,
        },
    )


def test_dead_letter_is_published():
    bus = FakeEventBus()

    publisher = DeadLetterPublisher(
        event_bus=bus,
        queue_name="rkjo.dlq",
    )

    dead_letter = publisher.publish(
        original_message=make_message(),
        reason="max_attempts_reached",
    )

    assert len(bus.messages) == 1

    queue, message = bus.messages[0]

    assert queue == "rkjo.dlq"
    assert message.message_type == (
        "workflow.step.dead_letter"
    )
    assert message.correlation_id == "corr-001"

    assert message.metadata[
        "original_message_id"
    ] == "original-001"

    assert message.metadata[
        "attempt"
    ] == 3

    assert dead_letter.payload[
        "reason"
    ] == "max_attempts_reached"


def test_empty_dlq_name_is_rejected():
    with pytest.raises(
        ValueError,
        match="queue_name",
    ):
        DeadLetterPublisher(
            event_bus=FakeEventBus(),
            queue_name=" ",
        )
