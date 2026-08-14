from typing import Any

import pytest

from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.workflow.async_dispatch import AsyncWorkflowDispatcher
from rkjo_kernel.workflow.models.workflow_context import WorkflowContext
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep


class FakeEventBus(EventBus):
    def __init__(self) -> None:
        self.published: list[
            tuple[str, AgentMessage]
        ] = []

    def publish(
        self,
        queue_name: str,
        message: str,
    ) -> None:
        pass

    def consume(
        self,
        queue_name: str,
        callback,
    ) -> None:
        pass

    def publish_agent_message(
        self,
        queue_name: str,
        message: AgentMessage,
    ) -> None:
        self.published.append(
            (queue_name, message)
        )

    def consume_agent_messages(
        self,
        queue_name: str,
        callback,
    ) -> None:
        pass

    def close(self) -> None:
        pass


def make_step() -> WorkflowStep:
    return WorkflowStep(
        step_id="weather",
        name="Weather",
        capability_name="weather.analysis",
    )


def test_dispatch_publishes_agent_message():
    bus = FakeEventBus()
    dispatcher = AsyncWorkflowDispatcher(
        event_bus=bus
    )

    context = WorkflowContext(
        input_data={
            "parcel_id": "P-100",
        },
        metadata={
            "product": "ADIP",
        },
    )

    result = dispatcher.dispatch(
        step=make_step(),
        context=context,
        queue_name="weather.queue",
        execution_id="execution-001",
        correlation_id="corr-001",
    )

    assert len(bus.published) == 1

    queue_name, message = bus.published[0]

    assert queue_name == "weather.queue"
    assert message.message_type == (
        "workflow.step.execute"
    )
    assert message.correlation_id == "corr-001"

    assert message.metadata[
        "workflow_execution_id"
    ] == "execution-001"

    assert message.metadata[
        "workflow_step_id"
    ] == "weather"

    assert message.metadata[
        "capability_name"
    ] == "weather.analysis"

    assert message.payload[
        "input_data"
    ] == {
        "parcel_id": "P-100"
    }

    assert result.message_id == message.message_id
    assert result.queue_name == "weather.queue"


def test_dispatch_generates_correlation_id():
    bus = FakeEventBus()
    dispatcher = AsyncWorkflowDispatcher(
        event_bus=bus
    )

    result = dispatcher.dispatch(
        step=make_step(),
        context=WorkflowContext(),
        queue_name="weather.queue",
        execution_id="execution-001",
    )

    assert result.correlation_id
    assert (
        result.correlation_id
        == bus.published[0][1].correlation_id
    )


def test_dispatch_rejects_empty_queue():
    dispatcher = AsyncWorkflowDispatcher(
        event_bus=FakeEventBus()
    )

    with pytest.raises(
        ValueError,
        match="queue_name must not be empty",
    ):
        dispatcher.dispatch(
            step=make_step(),
            context=WorkflowContext(),
            queue_name=" ",
            execution_id="execution-001",
        )
