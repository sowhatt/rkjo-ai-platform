from collections import defaultdict
from collections.abc import Callable
from typing import Any

from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.orchestrator.orchestrator import (
    AgentOrchestrator,
    MissionRequest,
)
from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
from rkjo_kernel.registry.discovery import AgentDiscovery
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.runtime.agent_runtime import AgentRuntime
from rkjo_kernel.services.registry_service import RegistryService

from rkjo_worker.main import PlatformWorkerAgent


class InMemoryEventBus(EventBus):
    def __init__(self) -> None:
        self._text_consumers: dict[str, Callable[[str], None]] = {}
        self._agent_consumers: dict[
            str,
            Callable[[AgentMessage], Any],
        ] = {}

        self.published_messages: dict[
            str,
            list[AgentMessage],
        ] = defaultdict(list)

        self.results: dict[str, Any] = {}
        self.closed = False

    def publish(
        self,
        queue_name: str,
        message: str,
    ) -> None:
        consumer = self._text_consumers.get(queue_name)
        if consumer is not None:
            consumer(message)

    def consume(
        self,
        queue_name: str,
        callback: Callable[[str], None],
    ) -> None:
        self._text_consumers[queue_name] = callback

    def publish_agent_message(
        self,
        queue_name: str,
        message: AgentMessage,
    ) -> None:
        self.published_messages[queue_name].append(message)

        consumer = self._agent_consumers.get(queue_name)
        if consumer is not None:
            self.results[message.message_id] = consumer(message)

    def consume_agent_messages(
        self,
        queue_name: str,
        callback: Callable[[AgentMessage], Any],
    ) -> None:
        self._agent_consumers[queue_name] = callback

    def register_agent_consumer(
        self,
        queue_name: str,
        callback: Callable[[AgentMessage], Any],
    ) -> None:
        self._agent_consumers[queue_name] = callback

    def close(self) -> None:
        self.closed = True


def test_mission_is_discovered_dispatched_and_executed() -> None:
    bus = InMemoryEventBus()

    registry = AgentRegistry()
    registry_service = RegistryService(registry)

    agent_name = "rkjo.education.test_worker"
    queue_name = "rkjo.education.test_worker.queue"
    capability_name = "education.tutoring"

    descriptor = AgentDescriptor(
        name=agent_name,
        display_name="RKJO Education Test Worker",
        version="1.0.0",
        description="E2E education tutoring worker.",
        product="RKJO Education",
        queue_name=queue_name,
        status=AgentStatus.AVAILABLE,
        capabilities=[
            AgentCapability(
                name=capability_name,
                description="Provide tutoring assistance.",
                confidence_score=0.95,
                estimated_cost=0.01,
                average_duration_ms=100,
                tags=["education", "tutoring"],
            )
        ],
        priority=8,
    )

    registry_service.register_agent(descriptor)

    discovery = AgentDiscovery(
        registry_service=registry_service,
    )

    agent = PlatformWorkerAgent(
        agent_name=agent_name,
        queue_name=queue_name,
        event_bus=bus,
    )

    runtime = AgentRuntime(
        agent=agent,
        event_bus=bus,
        registry_service=registry_service,
    )

    bus.register_agent_consumer(
        queue_name=queue_name,
        callback=runtime.execute,
    )

    orchestrator = AgentOrchestrator(
        discovery=discovery,
        event_bus=bus,
    )

    request = MissionRequest(
        capability_name=capability_name,
        payload={
            "student_level": "CE1",
            "subject": "mathematics",
            "question": "Comment calculer 27 + 18 ?",
        },
        product="RKJO Education",
        source="rkjo.education.e2e",
        correlation_id="e2e-education-001",
        metadata={
            "test_type": "mission_execution",
        },
    )

    dispatch = orchestrator.dispatch(request)

    assert dispatch.discovery.agent.name == agent_name
    assert dispatch.discovery.capability.name == capability_name
    assert dispatch.queue_name == queue_name

    assert dispatch.message.target == agent_name
    assert dispatch.message.correlation_id == request.correlation_id

    assert (
        dispatch.message.metadata["requested_capability"]
        == capability_name
    )

    assert dispatch.message.metadata["product"] == "RKJO Education"

    assert len(bus.published_messages[queue_name]) == 1

    published_message = bus.published_messages[queue_name][0]

    assert published_message.message_id == dispatch.message.message_id

    result = bus.results[dispatch.message.message_id]

    assert result["processed_by"] == agent_name
    assert result["message_id"] == dispatch.message.message_id
    assert result["payload"] == request.payload

    assert agent.processed_messages == 1
    assert agent.failed_messages == 0
    assert runtime.total_runtime_messages == 1
