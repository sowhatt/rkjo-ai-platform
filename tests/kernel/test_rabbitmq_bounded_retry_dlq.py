from types import SimpleNamespace
from unittest.mock import Mock

import pika
import pytest

from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
from rkjo_kernel.messages.agent_message import AgentMessage


class FakeChannel:
    def __init__(self) -> None:
        self.declared = []
        self.published = []
        self.acked = []
        self.consumer_callback = None
        self.publish_error = None

    def queue_declare(self, *, queue, durable):
        self.declared.append((queue, durable))

    def basic_qos(self, *, prefetch_count):
        assert prefetch_count == 1

    def basic_consume(
        self,
        *,
        queue,
        on_message_callback,
        auto_ack,
    ):
        assert auto_ack is False
        self.consumer_callback = on_message_callback

    def start_consuming(self):
        return None

    def basic_publish(
        self,
        *,
        exchange,
        routing_key,
        body,
        properties,
        mandatory=False,
    ):
        if self.publish_error is not None:
            raise self.publish_error

        self.published.append(
            {
                "exchange": exchange,
                "routing_key": routing_key,
                "body": body,
                "properties": properties,
                "mandatory": mandatory,
            }
        )

    def basic_ack(self, *, delivery_tag):
        self.acked.append(delivery_tag)


def make_bus(
    *,
    max_delivery_attempts: int = 3,
) -> tuple[RabbitMQEventBus, FakeChannel]:
    bus = RabbitMQEventBus.__new__(RabbitMQEventBus)
    bus.max_delivery_attempts = max_delivery_attempts
    bus.dlq_suffix = ".dlq"
    bus.logger = Mock()

    channel = FakeChannel()
    bus.channel = channel

    return bus, channel


def make_message() -> AgentMessage:
    return AgentMessage(
        message_id="retry-message-001",
        correlation_id="retry-correlation-001",
        source="agent.source",
        target="rkjo.workflow",
        message_type="workflow.step.result",
        payload={
            "success": True,
            "result": {"value": "ok"},
        },
        metadata={
            "workflow_execution_id": "execution-001",
            "workflow_step_id": "step-1",
        },
    )


def invoke_delivery(
    channel: FakeChannel,
    *,
    body: bytes,
    headers=None,
    delivery_tag: int = 10,
):
    assert channel.consumer_callback is not None

    properties = pika.BasicProperties(
        content_type="application/json",
        delivery_mode=pika.DeliveryMode.Persistent,
        headers=headers or {},
        message_id="retry-message-001",
        correlation_id="retry-correlation-001",
        type="workflow.step.result",
    )

    method = SimpleNamespace(
        delivery_tag=delivery_tag,
    )

    channel.consumer_callback(
        channel,
        method,
        properties,
        body,
    )


def test_successful_agent_message_is_acked_without_retry():
    bus, channel = make_bus()
    callback = Mock()

    bus.consume_agent_messages(
        queue_name="rkjo.workflow.results",
        callback=callback,
    )

    message = make_message()
    invoke_delivery(
        channel,
        body=message.model_dump_json().encode("utf-8"),
    )

    callback.assert_called_once()
    assert channel.published == []
    assert channel.acked == [10]


def test_failed_agent_message_is_republished_with_incremented_attempt():
    bus, channel = make_bus(
        max_delivery_attempts=3,
    )

    def fail(_message):
        raise RuntimeError("temporary failure")

    bus.consume_agent_messages(
        queue_name="rkjo.workflow.results",
        callback=fail,
    )

    message = make_message()
    invoke_delivery(
        channel,
        body=message.model_dump_json().encode("utf-8"),
        headers={"x-rkjo-delivery-attempt": 1},
    )

    assert len(channel.published) == 1
    published = channel.published[0]

    assert published["routing_key"] == (
        "rkjo.workflow.results"
    )
    assert published["mandatory"] is True
    assert published["body"] == (
        message.model_dump_json().encode("utf-8")
    )
    assert (
        published["properties"].headers[
            "x-rkjo-delivery-attempt"
        ]
        == 2
    )
    assert (
        published["properties"].headers[
            "x-rkjo-original-queue"
        ]
        == "rkjo.workflow.results"
    )
    assert channel.acked == [10]


def test_failed_agent_message_moves_to_dlq_after_max_attempts():
    bus, channel = make_bus(
        max_delivery_attempts=3,
    )

    def fail(_message):
        raise RuntimeError("permanent failure")

    bus.consume_agent_messages(
        queue_name="rkjo.workflow.results",
        callback=fail,
    )

    message = make_message()
    invoke_delivery(
        channel,
        body=message.model_dump_json().encode("utf-8"),
        headers={"x-rkjo-delivery-attempt": 3},
    )

    assert len(channel.published) == 1
    published = channel.published[0]

    assert published["routing_key"] == (
        "rkjo.workflow.results.dlq"
    )
    assert published["mandatory"] is True
    assert (
        published["properties"].headers[
            "x-rkjo-delivery-attempt"
        ]
        == 3
    )
    assert (
        published["properties"].headers[
            "x-rkjo-failure-type"
        ]
        == "RuntimeError"
    )
    assert (
        published["properties"].headers[
            "x-rkjo-failure-message"
        ]
        == "permanent failure"
    )
    assert channel.acked == [10]


def test_invalid_json_is_dead_lettered_instead_of_looping_forever():
    bus, channel = make_bus(
        max_delivery_attempts=3,
    )
    callback = Mock()

    bus.consume_agent_messages(
        queue_name="rkjo.workflow.results",
        callback=callback,
    )

    invalid_body = b"not-valid-json"

    invoke_delivery(
        channel,
        body=invalid_body,
        headers={"x-rkjo-delivery-attempt": 3},
    )

    callback.assert_not_called()
    assert len(channel.published) == 1
    assert channel.published[0]["routing_key"] == (
        "rkjo.workflow.results.dlq"
    )
    assert channel.published[0]["mandatory"] is True
    assert channel.published[0]["body"] == invalid_body
    assert channel.acked == [10]


def test_original_delivery_is_not_acked_when_retry_publish_fails():
    bus, channel = make_bus(
        max_delivery_attempts=3,
    )

    def fail(_message):
        raise RuntimeError("handler failure")

    bus.consume_agent_messages(
        queue_name="rkjo.workflow.results",
        callback=fail,
    )

    channel.publish_error = RuntimeError(
        "broker publish failure"
    )

    message = make_message()

    with pytest.raises(
        RuntimeError,
        match="broker publish failure",
    ):
        invoke_delivery(
            channel,
            body=message.model_dump_json().encode("utf-8"),
            headers={"x-rkjo-delivery-attempt": 1},
        )

    assert channel.acked == []


@pytest.mark.parametrize(
    "max_delivery_attempts",
    [0, -1],
)
def test_bus_rejects_invalid_max_delivery_attempts(
    max_delivery_attempts,
):
    with pytest.raises(
        ValueError,
        match="max_delivery_attempts",
    ):
        RabbitMQEventBus(
            max_delivery_attempts=max_delivery_attempts
        )
