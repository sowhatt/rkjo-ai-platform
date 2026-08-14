from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.runtime.result_publisher import (
    AgentResultPublisher,
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


def make_request():
    return AgentMessage(
        source="rkjo.workflow",
        target="weather.agent",
        message_type="workflow.step.execute",
        correlation_id="corr-001",
        payload={},
        metadata={
            "reply_queue": "workflow.results",
            "workflow_execution_id": "exec-001",
            "workflow_step_id": "weather",
        },
    )


def test_publish_success():
    bus = FakeEventBus()

    publisher = AgentResultPublisher(
        event_bus=bus,
        source="weather.agent",
    )

    request = make_request()

    response = publisher.publish_success(
        request=request,
        result={"temperature": 31},
    )

    assert response is not None
    assert len(bus.messages) == 1

    queue, message = bus.messages[0]

    assert queue == "workflow.results"
    assert message.message_type == (
        "workflow.step.result"
    )

    assert message.correlation_id == (
        request.correlation_id
    )

    assert message.payload == {
        "success": True,
        "result": {
            "temperature": 31
        },
    }

    assert message.metadata[
        "workflow_execution_id"
    ] == "exec-001"


def test_publish_failure():
    bus = FakeEventBus()

    publisher = AgentResultPublisher(
        event_bus=bus,
        source="weather.agent",
    )

    response = publisher.publish_failure(
        request=make_request(),
        error=RuntimeError("boom"),
    )

    assert response is not None

    assert response.payload == {
        "success": False,
        "error": "boom",
    }


def test_no_reply_queue_means_no_response():
    bus = FakeEventBus()

    publisher = AgentResultPublisher(
        event_bus=bus,
        source="weather.agent",
    )

    request = AgentMessage(
        source="rkjo.workflow",
        target="weather.agent",
        payload={},
    )

    response = publisher.publish_success(
        request=request,
        result={},
    )

    assert response is None
    assert bus.messages == []
