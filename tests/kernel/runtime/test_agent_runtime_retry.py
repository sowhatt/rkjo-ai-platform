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
from rkjo_kernel.runtime.retry_policy import RetryPolicy
from rkjo_kernel.services.registry_service import RegistryService


class FakeEventBus(EventBus):
    def publish(self, queue_name, message):
        pass

    def consume(self, queue_name, callback):
        pass

    def publish_agent_message(
        self,
        queue_name,
        message,
    ):
        pass

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


class InvalidPayloadAgent(BaseAgent):
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
            display_name="Retry Agent",
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
        source="rkjo.workflow",
        target=agent_name,
        message_type="workflow.step.execute",
        payload={},
        metadata={
            "attempt": attempt,
        },
    )


def test_runtime_marks_timeout_as_retryable():
    bus = FakeEventBus()

    agent = TimeoutAgent(
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
            max_attempts=3,
            base_delay_seconds=1.0,
        ),
    )

    message = make_message(
        agent.agent_name,
        attempt=1,
    )

    with pytest.raises(
        TimeoutError
    ):
        runtime.execute(message)

    assert message.metadata[
        "retry_should_retry"
    ] is True

    assert message.metadata[
        "retry_attempt"
    ] == 1

    assert message.metadata[
        "retry_delay_seconds"
    ] == 1.0

    assert message.metadata[
        "retry_reason"
    ] == "retryable_error"


def test_runtime_stops_retry_at_max_attempts():
    bus = FakeEventBus()

    agent = TimeoutAgent(
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
            max_attempts=3,
        ),
    )

    message = make_message(
        agent.agent_name,
        attempt=3,
    )

    with pytest.raises(
        TimeoutError
    ):
        runtime.execute(message)

    assert message.metadata[
        "retry_should_retry"
    ] is False

    assert message.metadata[
        "retry_reason"
    ] == "max_attempts_reached"


def test_runtime_marks_value_error_as_permanent():
    bus = FakeEventBus()

    agent = InvalidPayloadAgent(
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
        retry_policy=RetryPolicy(),
    )

    message = make_message(
        agent.agent_name,
    )

    with pytest.raises(
        ValueError
    ):
        runtime.execute(message)

    assert message.metadata[
        "retry_should_retry"
    ] is False

    assert message.metadata[
        "retry_reason"
    ] == "permanent_error"


def test_runtime_remains_compatible_without_retry_policy():
    bus = FakeEventBus()

    agent = TimeoutAgent(
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
    )

    message = make_message(
        agent.agent_name,
    )

    with pytest.raises(
        TimeoutError
    ):
        runtime.execute(message)

    assert "retry_should_retry" not in (
        message.metadata
    )
