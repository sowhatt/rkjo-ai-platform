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
from rkjo_kernel.runtime.result_publisher import AgentResultPublisher
from rkjo_kernel.services.registry_service import RegistryService


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


class SuccessAgent(BaseAgent):
    def process(self, message):
        return {
            "temperature": 31
        }


class FailureAgent(BaseAgent):
    def process(self, message):
        raise RuntimeError(
            "weather unavailable"
        )


def make_registry(agent_name):
    agent_registry = AgentRegistry()

    service = RegistryService(
        registry=agent_registry
    )

    service.register_agent(
        AgentDescriptor(
            name=agent_name,
            display_name="Weather Agent",
            product="ADIP",
            queue_name="weather.queue",
            status=AgentStatus.AVAILABLE,
        )
    )

    return service


def make_message(agent_name):
    return AgentMessage(
        source="rkjo.workflow",
        target=agent_name,
        message_type="workflow.step.execute",
        correlation_id="corr-001",
        payload={},
        metadata={
            "reply_queue": "workflow.results",
            "workflow_execution_id": "exec-001",
            "workflow_step_id": "weather",
        },
    )


def test_runtime_publishes_success_result():
    bus = FakeEventBus()

    agent = SuccessAgent(
        agent_name="weather.agent",
        queue_name="weather.queue",
        event_bus=bus,
    )

    publisher = AgentResultPublisher(
        event_bus=bus,
        source=agent.agent_name,
    )

    runtime = AgentRuntime(
        agent=agent,
        event_bus=bus,
        registry_service=make_registry(
            agent.agent_name
        ),
        result_publisher=publisher,
    )

    result = runtime.execute(
        make_message(agent.agent_name)
    )

    assert result == {
        "temperature": 31
    }

    assert len(bus.messages) == 1

    queue, response = bus.messages[0]

    assert queue == "workflow.results"
    assert response.message_type == (
        "workflow.step.result"
    )

    assert response.payload == {
        "success": True,
        "result": {
            "temperature": 31
        },
    }


def test_runtime_publishes_failure_result():
    bus = FakeEventBus()

    agent = FailureAgent(
        agent_name="weather.agent",
        queue_name="weather.queue",
        event_bus=bus,
    )

    publisher = AgentResultPublisher(
        event_bus=bus,
        source=agent.agent_name,
    )

    runtime = AgentRuntime(
        agent=agent,
        event_bus=bus,
        registry_service=make_registry(
            agent.agent_name
        ),
        result_publisher=publisher,
    )

    with pytest.raises(
        RuntimeError,
        match="weather unavailable",
    ):
        runtime.execute(
            make_message(
                agent.agent_name
            )
        )

    assert len(bus.messages) == 1

    queue, response = bus.messages[0]

    assert queue == "workflow.results"

    assert response.payload == {
        "success": False,
        "error": "weather unavailable",
    }


def test_runtime_remains_compatible_without_result_publisher():
    bus = FakeEventBus()

    agent = SuccessAgent(
        agent_name="weather.agent",
        queue_name="weather.queue",
        event_bus=bus,
    )

    runtime = AgentRuntime(
        agent=agent,
        event_bus=bus,
        registry_service=make_registry(
            agent.agent_name
        ),
    )

    result = runtime.execute(
        make_message(agent.agent_name)
    )

    assert result == {
        "temperature": 31
    }

    assert bus.messages == []
