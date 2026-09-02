from collections import defaultdict
from collections.abc import Callable
from typing import Any

from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.registry.descriptor import AgentDescriptor, AgentStatus
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.runtime.agent_runtime import AgentRuntime
from rkjo_kernel.runtime.result_publisher import AgentResultPublisher
from rkjo_kernel.services.registry_service import RegistryService

from rkjo_worker.main import PlatformWorkerAgent


class InMemoryEventBus(EventBus):
    def __init__(self) -> None:
        self.agent_consumers: dict[
            str,
            Callable[[AgentMessage], Any],
        ] = {}

        self.published_messages: dict[
            str,
            list[AgentMessage],
        ] = defaultdict(list)

        self.closed = False

    def publish(
        self,
        queue_name: str,
        message: str,
    ) -> None:
        pass

    def consume(
        self,
        queue_name: str,
        callback: Callable[[str], None],
    ) -> None:
        pass

    def publish_agent_message(
        self,
        queue_name: str,
        message: AgentMessage,
    ) -> None:
        self.published_messages[queue_name].append(message)

        consumer = self.agent_consumers.get(queue_name)

        if consumer is not None:
            consumer(message)

    def consume_agent_messages(
        self,
        queue_name: str,
        callback: Callable[[AgentMessage], Any],
    ) -> None:
        self.agent_consumers[queue_name] = callback

    def close(self) -> None:
        self.closed = True


def test_runtime_publishes_async_workflow_result() -> None:
    bus = InMemoryEventBus()

    registry = AgentRegistry()
    registry_service = RegistryService(registry)

    agent_name = "rkjo.education.async_worker"
    queue_name = "rkjo.education.async_worker.queue"
    reply_queue = "rkjo.workflow.results"

    descriptor = AgentDescriptor(
        name=agent_name,
        display_name="RKJO Education Async Worker",
        version="1.0.0",
        description="Async E2E worker.",
        product="RKJO Education",
        queue_name=queue_name,
        status=AgentStatus.AVAILABLE,
        capabilities=[
            AgentCapability(
                name="education.tutoring",
                description="Tutoring capability.",
                confidence_score=0.95,
                estimated_cost=0.01,
                average_duration_ms=100,
            )
        ],
        priority=8,
    )

    registry_service.register_agent(descriptor)

    agent = PlatformWorkerAgent(
        agent_name=agent_name,
        queue_name=queue_name,
        event_bus=bus,
    )

    result_publisher = AgentResultPublisher(
        event_bus=bus,
        source=agent_name,
    )

    runtime = AgentRuntime(
        agent=agent,
        event_bus=bus,
        registry_service=registry_service,
        result_publisher=result_publisher,
    )

    request = AgentMessage(
        source="rkjo.workflow",
        target=agent_name,
        message_type="mission",
        correlation_id="corr-education-001",
        payload={
            "student_level": "CE1",
            "subject": "mathematics",
            "question": "Combien font 27 + 18 ?",
        },
        metadata={
            "reply_queue": reply_queue,
            "workflow_execution_id": "workflow-exec-001",
            "workflow_step_id": "step-tutoring-001",
        },
    )

    result = runtime.execute(request)

    assert reply_queue in bus.published_messages
    assert len(bus.published_messages[reply_queue]) == 1

    response = bus.published_messages[reply_queue][0]

    assert response.message_type == "workflow.step.result"
    assert response.target == "rkjo.workflow"
    assert response.source == agent_name

    assert response.correlation_id == request.correlation_id

    assert response.payload["success"] is True
    assert response.payload["result"]["processed_by"] == agent_name
    assert response.payload["result"]["message_id"] == request.message_id
    assert response.payload["result"]["payload"] == request.payload

    assert (
        response.metadata["request_message_id"]
        == request.message_id
    )

    assert (
        response.metadata["workflow_execution_id"]
        == "workflow-exec-001"
    )

    assert (
        response.metadata["workflow_step_id"]
        == "step-tutoring-001"
    )
