from typing import Any

from rkjo_kernel.agents.base_agent import BaseAgent
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.runtime.agent_runtime import AgentRuntime
from rkjo_kernel.runtime.status import RuntimeStatus
from rkjo_kernel.services.registry_service import RegistryService


class FakeEventBus:
    """
    Faux bus permettant de tester le Runtime sans RabbitMQ.
    """

    def __init__(self) -> None:
        self.callback = None
        self.queue_name = None
        self.closed = False

    def consume_agent_messages(
        self,
        queue_name: str,
        callback,
    ) -> None:
        self.queue_name = queue_name
        self.callback = callback

    def publish_agent_message(
        self,
        queue_name: str,
        message: AgentMessage,
    ) -> None:
        raise NotImplementedError

    def publish(
        self,
        queue_name: str,
        message: str,
    ) -> None:
        raise NotImplementedError

    def consume(
        self,
        queue_name: str,
        callback,
    ) -> None:
        raise NotImplementedError

    def close(self) -> None:
        self.closed = True


class DemoRuntimeAgent(BaseAgent):
    """
    Agent métier minimal utilisé pour tester le Runtime.
    """

    def process(
        self,
        message: AgentMessage,
    ) -> Any:
        return {
            "question": message.payload["question"],
            "processed": True,
        }


class FailingRuntimeAgent(BaseAgent):
    """
    Agent simulant un échec métier.
    """

    def process(
        self,
        message: AgentMessage,
    ) -> Any:
        raise RuntimeError("Simulated agent failure.")


def create_runtime(
    failing: bool = False,
):
    registry = AgentRegistry()
    service = RegistryService(registry)
    event_bus = FakeEventBus()

    descriptor = AgentDescriptor(
        name="adip.runtime_agent",
        display_name="Runtime Agent",
        product="ADIP",
        queue_name="adip.runtime",
        status=AgentStatus.STOPPED,
    )

    service.register_agent(descriptor)

    agent_class = (
        FailingRuntimeAgent
        if failing
        else DemoRuntimeAgent
    )

    agent = agent_class(
        agent_name="adip.runtime_agent",
        queue_name="adip.runtime",
        event_bus=event_bus,
    )

    runtime = AgentRuntime(
        agent=agent,
        event_bus=event_bus,
        registry_service=service,
    )

    return service, event_bus, runtime


def create_message() -> AgentMessage:
    return AgentMessage(
        source="rkjo.orchestrator",
        target="adip.runtime_agent",
        payload={
            "question": "Analyse cette mission."
        },
    )


def test_runtime_initial_state():
    service, _, runtime = create_runtime()

    health = runtime.health()

    assert (
        health["runtime_status"]
        == RuntimeStatus.CREATED.value
    )
    assert health["total_runtime_messages"] == 0
    assert health["last_error"] is None

    descriptor = service.get_agent(
        "adip.runtime_agent"
    )

    assert descriptor is not None
    assert descriptor.status == AgentStatus.STOPPED


def test_runtime_processes_message():
    service, _, runtime = create_runtime()

    runtime._handle_message(
        create_message()
    )

    health = runtime.health()

    assert health["total_runtime_messages"] == 1
    assert health["last_duration_ms"] is not None
    assert health["last_error"] is None

    descriptor = service.get_agent(
        "adip.runtime_agent"
    )

    assert descriptor is not None
    assert descriptor.status == AgentStatus.AVAILABLE


def test_runtime_marks_agent_error():
    service, _, runtime = create_runtime(
        failing=True
    )

    try:
        runtime._handle_message(
            create_message()
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError(
            "The failing agent should raise RuntimeError."
        )

    health = runtime.health()

    assert health["last_error"] == (
        "Simulated agent failure."
    )

    descriptor = service.get_agent(
        "adip.runtime_agent"
    )

    assert descriptor is not None
    assert descriptor.status == AgentStatus.ERROR


def test_runtime_stop_closes_event_bus():
    service, event_bus, runtime = create_runtime()

    runtime.status = RuntimeStatus.RUNNING
    runtime.stop()

    assert event_bus.closed is True
    assert runtime.status == RuntimeStatus.STOPPED

    descriptor = service.get_agent(
        "adip.runtime_agent"
    )

    assert descriptor is not None
    assert descriptor.status == AgentStatus.STOPPED

def test_runtime_recovers_after_previous_error():
    service, _, runtime = create_runtime()

    runtime.last_error = "Previous failure"

    runtime._handle_message(
        create_message()
    )

    health = runtime.health()

    assert health["last_error"] is None
    assert health["total_runtime_messages"] == 1

    descriptor = service.get_agent(
        "adip.runtime_agent"
    )

    assert descriptor is not None
    assert descriptor.status == AgentStatus.AVAILABLE
