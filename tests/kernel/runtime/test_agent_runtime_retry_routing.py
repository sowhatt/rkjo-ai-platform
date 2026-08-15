import pytest

from rkjo_kernel.agents.base_agent import BaseAgent
from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.runtime.agent_runtime import AgentRuntime
from rkjo_kernel.runtime.dead_letter_publisher import (
    DeadLetterPublisher,
)
from rkjo_kernel.runtime.result_publisher import (
    AgentResultPublisher,
)
from rkjo_kernel.runtime.retry_policy import RetryPolicy
from rkjo_kernel.services.registry_service import (
    RegistryService,
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


class TimeoutAgent(BaseAgent):
    def process(self, message):
        raise TimeoutError(
            "provider timeout"
        )


class InvalidAgent(BaseAgent):
    def process(self, message):
        raise ValueError(
            "invalid payload"
        )


def make_registry(agent_name):
    registry = AgentRegistry()

    service = RegistryService(
        registry=registry
    )

    service.register_agent(
        AgentDescriptor(
            name=agent_name,
            display_name="Retry Routing Agent",
            product="ADIP",
            queue_name="retry.queue",
            status=AgentStatus.AVAILABLE,
        )
    )

    return service


def make_message(
    agent_name,
    *,
    attempt=1,
):
    return AgentMessage(
        message_id=f"message-{attempt}",
        correlation_id="corr-001",
        source="rkjo.workflow",
        target=agent_name,
        message_type="workflow.step.execute",
        payload={},
        metadata={
            "attempt": attempt,
            "reply_queue": "workflow.results",
            "workflow_execution_id": "exec-001",
            "workflow_step_id": "weather",
        },
    )


def make_runtime(
    *,
    agent,
    bus,
    max_attempts=3,
):
    return AgentRuntime(
        agent=agent,
        event_bus=bus,
        registry_service=make_registry(
            agent.agent_name
        ),
        retry_policy=RetryPolicy(
            max_attempts=max_attempts,
            base_delay_seconds=0,
        ),
        result_publisher=AgentResultPublisher(
            event_bus=bus,
            source=agent.agent_name,
        ),
        dead_letter_publisher=DeadLetterPublisher(
            event_bus=bus,
            queue_name="retry.queue.dlq",
        ),
    )


def test_retryable_failure_republishes_new_message():
    bus = FakeEventBus()

    agent = TimeoutAgent(
        agent_name="retry.agent",
        queue_name="retry.queue",
        event_bus=bus,
    )

    runtime = make_runtime(
        agent=agent,
        bus=bus,
    )

    original = make_message(
        agent.agent_name,
        attempt=1,
    )

    result = runtime._consume_message(
        original
    )

    assert result is None
    assert len(bus.messages) == 1

    queue, retry = bus.messages[0]

    assert queue == "retry.queue"

    assert retry.message_id != (
        original.message_id
    )

    assert retry.correlation_id == (
        original.correlation_id
    )

    assert retry.metadata["attempt"] == 2

    assert retry.metadata[
        "retry_of_message_id"
    ] == original.message_id

    # No workflow failure result must be emitted yet.
    assert all(
        message.message_type
        != "workflow.step.result"
        for _, message in bus.messages
    )


def test_max_attempts_publishes_failure_and_dlq():
    bus = FakeEventBus()

    agent = TimeoutAgent(
        agent_name="retry.agent",
        queue_name="retry.queue",
        event_bus=bus,
    )

    runtime = make_runtime(
        agent=agent,
        bus=bus,
        max_attempts=3,
    )

    result = runtime._consume_message(
        make_message(
            agent.agent_name,
            attempt=3,
        )
    )

    assert result is None

    message_types = [
        message.message_type
        for _, message in bus.messages
    ]

    assert "workflow.step.result" in (
        message_types
    )

    assert "workflow.step.dead_letter" in (
        message_types
    )

    dlq_messages = [
        (queue, message)
        for queue, message in bus.messages
        if message.message_type
        == "workflow.step.dead_letter"
    ]

    assert len(dlq_messages) == 1

    queue, dlq_message = dlq_messages[0]

    assert queue == "retry.queue.dlq"

    assert dlq_message.payload[
        "reason"
    ] == "max_attempts_reached"


def test_permanent_failure_goes_directly_to_dlq():
    bus = FakeEventBus()

    agent = InvalidAgent(
        agent_name="retry.agent",
        queue_name="retry.queue",
        event_bus=bus,
    )

    runtime = make_runtime(
        agent=agent,
        bus=bus,
    )

    result = runtime._consume_message(
        make_message(
            agent.agent_name,
            attempt=1,
        )
    )

    assert result is None

    dead_letters = [
        message
        for _, message in bus.messages
        if message.message_type
        == "workflow.step.dead_letter"
    ]

    assert len(dead_letters) == 1

    assert dead_letters[0].payload[
        "reason"
    ] == "permanent_error"


def test_execute_still_raises_for_local_callers():
    bus = FakeEventBus()

    agent = TimeoutAgent(
        agent_name="retry.agent",
        queue_name="retry.queue",
        event_bus=bus,
    )

    runtime = make_runtime(
        agent=agent,
        bus=bus,
    )

    with pytest.raises(
        TimeoutError,
        match="provider timeout",
    ):
        runtime.execute(
            make_message(
                agent.agent_name
            )
        )


def test_without_dead_letter_publisher_terminal_error_raises():
    bus = FakeEventBus()

    agent = InvalidAgent(
        agent_name="retry.agent",
        queue_name="retry.queue",
        event_bus=bus,
    )

    runtime = AgentRuntime(
        agent=agent,
        event_bus=bus,
        registry_service=make_registry(
            agent.agent_name
        ),
        retry_policy=RetryPolicy(
            base_delay_seconds=0
        ),
    )

    with pytest.raises(
        ValueError,
        match="invalid payload",
    ):
        runtime._consume_message(
            make_message(
                agent.agent_name
            )
        )
