from collections import defaultdict
from collections.abc import Callable
from typing import Any

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
from rkjo_kernel.workflow.agent_routing import WorkflowAgentRouter
from rkjo_kernel.workflow.async_coordinator import AsyncWorkflowCoordinator
from rkjo_kernel.workflow.async_dispatch import AsyncWorkflowDispatcher
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.models.workflow_definition import WorkflowDefinition
from rkjo_kernel.workflow.models.workflow_status import WorkflowStatus
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep
from rkjo_kernel.workflow.repository.memory import InMemoryWorkflowRepository
from rkjo_kernel.workflow.result_handler import WorkflowResultHandler


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
        self.published_messages[
            queue_name
        ].append(message)

        consumer = self.agent_consumers.get(
            queue_name
        )

        if consumer is not None:
            consumer(message)

    def consume_agent_messages(
        self,
        queue_name: str,
        callback: Callable[[AgentMessage], Any],
    ) -> None:
        self.agent_consumers[
            queue_name
        ] = callback

    def close(self) -> None:
        self.closed = True


class DiagnosticAgent(BaseAgent):
    def process(
        self,
        message: AgentMessage,
    ) -> dict[str, Any]:
        return {
            "student_level": "beginner",
            "difficulty": "addition",
        }


class TutorAgent(BaseAgent):
    def process(
        self,
        message: AgentMessage,
    ) -> dict[str, Any]:
        outputs = message.payload["outputs"]

        assert outputs["diagnostic"] == {
            "student_level": "beginner",
            "difficulty": "addition",
        }

        return {
            "lesson": "addition-with-carry",
            "explanation": "27 + 18 = 45",
        }


class CapabilityTutorAgent(BaseAgent):
    def process(
        self,
        message: AgentMessage,
    ) -> dict[str, Any]:
        return {
            "lesson": "addition-with-carry",
            "explanation": "27 + 18 = 45",
        }


class ExerciseAgent(BaseAgent):
    def process(
        self,
        message: AgentMessage,
    ) -> dict[str, Any]:
        outputs = message.payload["outputs"]

        assert outputs["diagnostic"] == {
            "student_level": "beginner",
            "difficulty": "addition",
        }

        assert outputs["tutoring"] == {
            "lesson": "addition-with-carry",
            "explanation": "27 + 18 = 45",
        }

        return {
            "exercise": "34 + 29",
            "expected_answer": 63,
        }


def register_agent(
    service: RegistryService,
    *,
    name: str,
    queue_name: str,
) -> None:
    service.register_agent(
        AgentDescriptor(
            name=name,
            display_name=name,
            product="RKJO Education",
            queue_name=queue_name,
            status=AgentStatus.AVAILABLE,
        )
    )


def test_async_three_agent_workflow_auto_continues() -> None:
    bus = InMemoryEventBus()

    repository = InMemoryWorkflowRepository()

    engine = WorkflowEngine(
        repository=repository
    )

    registry = AgentRegistry()

    registry_service = RegistryService(
        registry=registry
    )

    agents = [
        (
            DiagnosticAgent,
            "education.diagnostic.agent",
            "education.diagnostic.queue",
        ),
        (
            TutorAgent,
            "education.tutor.agent",
            "education.tutor.queue",
        ),
        (
            ExerciseAgent,
            "education.exercise.agent",
            "education.exercise.queue",
        ),
    ]

    runtimes = []

    for (
        agent_class,
        agent_name,
        queue_name,
    ) in agents:
        register_agent(
            registry_service,
            name=agent_name,
            queue_name=queue_name,
        )

        agent = agent_class(
            agent_name=agent_name,
            queue_name=queue_name,
            event_bus=bus,
        )

        runtime = AgentRuntime(
            agent=agent,
            event_bus=bus,
            registry_service=registry_service,
            result_publisher=AgentResultPublisher(
                event_bus=bus,
                source=agent_name,
            ),
        )

        runtimes.append(runtime)

        bus.consume_agent_messages(
            queue_name=queue_name,
            callback=runtime.execute,
        )

    definition = WorkflowDefinition(
        workflow_id="education-learning-e2e",
        name="Education Learning E2E",
        steps=[
            WorkflowStep(
                step_id="diagnostic",
                name="Diagnostic",
                agent_name="education.diagnostic.agent",
                position=0,
            ),
            WorkflowStep(
                step_id="tutoring",
                name="Tutoring",
                agent_name="education.tutor.agent",
                position=1,
            ),
            WorkflowStep(
                step_id="exercise",
                name="Exercise",
                agent_name="education.exercise.agent",
                position=2,
            ),
        ],
    )

    execution = engine.create_execution(
        definition,
        execution_id="education-e2e-001",
        input_data={
            "student_id": "student-001",
            "subject": "mathematics",
            "question": "Combien font 27 + 18 ?",
        },
    )

    engine.start(execution)

    coordinator = AsyncWorkflowCoordinator(
        engine=engine,
        router=WorkflowAgentRouter(
            registry_service=registry_service
        ),
        dispatcher=AsyncWorkflowDispatcher(
            event_bus=bus
        ),
        reply_queue="rkjo.workflow.results",
    )

    result_handler = WorkflowResultHandler(
        engine=engine,
        coordinator=coordinator,
    )

    received_results = []

    def handle_result(
        message: AgentMessage,
    ) -> None:
        received_results.append(message)
        result_handler.handle(message)

    bus.consume_agent_messages(
        queue_name="rkjo.workflow.results",
        callback=handle_result,
    )

    #
    # Only the FIRST workflow step is explicitly dispatched.
    #
    # Tutoring and Exercise MUST be triggered automatically
    # through WorkflowResultHandler -> AsyncWorkflowCoordinator.
    #
    first_dispatch = coordinator.dispatch_next(
        execution,
        correlation_id="corr-education-e2e-001",
    )

    assert first_dispatch is not None
    assert first_dispatch.step_id == "diagnostic"

    restored = repository.get(
        execution.execution_id
    )

    assert restored is not None

    assert restored.status == WorkflowStatus.COMPLETED
    assert restored.current_step_id is None

    assert restored.context.outputs == {
        "diagnostic": {
            "student_level": "beginner",
            "difficulty": "addition",
        },
        "tutoring": {
            "lesson": "addition-with-carry",
            "explanation": "27 + 18 = 45",
        },
        "exercise": {
            "exercise": "34 + 29",
            "expected_answer": 63,
        },
    }

    assert len(received_results) == 3

    assert {
        message.metadata["workflow_step_id"]
        for message in received_results
    } == {
        "diagnostic",
        "tutoring",
        "exercise",
    }

    assert {
        message.correlation_id
        for message in received_results
    } == {
        "corr-education-e2e-001"
    }

    assert len(
        bus.published_messages[
            "education.diagnostic.queue"
        ]
    ) == 1

    assert len(
        bus.published_messages[
            "education.tutor.queue"
        ]
    ) == 1

    assert len(
        bus.published_messages[
            "education.exercise.queue"
        ]
    ) == 1

    assert all(
        runtime.total_runtime_messages == 1
        for runtime in runtimes
    )


def test_async_workflow_routes_capability_to_concrete_agent() -> None:
    bus = InMemoryEventBus()

    repository = InMemoryWorkflowRepository()

    engine = WorkflowEngine(
        repository=repository
    )

    registry = AgentRegistry()

    registry_service = RegistryService(
        registry=registry
    )

    from rkjo_kernel.registry.capability import AgentCapability

    capability = AgentCapability(
        name="education.tutoring",
        description="Education tutoring capability.",
    )

    registry_service.register_agent(
        AgentDescriptor(
            name="education.tutor.low",
            display_name="Low priority tutor",
            product="RKJO Education",
            queue_name="education.tutor.low.queue",
            status=AgentStatus.AVAILABLE,
            priority=3,
            capabilities=[capability],
        )
    )

    registry_service.register_agent(
        AgentDescriptor(
            name="education.tutor.high",
            display_name="High priority tutor",
            product="RKJO Education",
            queue_name="education.tutor.high.queue",
            status=AgentStatus.AVAILABLE,
            priority=9,
            capabilities=[capability],
        )
    )

    low_agent = CapabilityTutorAgent(
        agent_name="education.tutor.low",
        queue_name="education.tutor.low.queue",
        event_bus=bus,
    )

    high_agent = CapabilityTutorAgent(
        agent_name="education.tutor.high",
        queue_name="education.tutor.high.queue",
        event_bus=bus,
    )

    low_runtime = AgentRuntime(
        agent=low_agent,
        event_bus=bus,
        registry_service=registry_service,
        result_publisher=AgentResultPublisher(
            event_bus=bus,
            source=low_agent.agent_name,
        ),
    )

    high_runtime = AgentRuntime(
        agent=high_agent,
        event_bus=bus,
        registry_service=registry_service,
        result_publisher=AgentResultPublisher(
            event_bus=bus,
            source=high_agent.agent_name,
        ),
    )

    bus.consume_agent_messages(
        queue_name="education.tutor.low.queue",
        callback=low_runtime.execute,
    )

    bus.consume_agent_messages(
        queue_name="education.tutor.high.queue",
        callback=high_runtime.execute,
    )

    definition = WorkflowDefinition(
        workflow_id="education-capability-e2e",
        name="Education Capability Routing E2E",
        steps=[
            WorkflowStep(
                step_id="tutoring",
                name="Tutoring",
                capability_name="education.tutoring",
                position=0,
            ),
        ],
    )

    execution = engine.create_execution(
        definition,
        execution_id="education-capability-e2e-001",
        input_data={
            "student_id": "student-001",
            "subject": "mathematics",
        },
    )

    engine.start(execution)

    coordinator = AsyncWorkflowCoordinator(
        engine=engine,
        router=WorkflowAgentRouter(
            registry_service=registry_service
        ),
        dispatcher=AsyncWorkflowDispatcher(
            event_bus=bus
        ),
        reply_queue="rkjo.workflow.results",
    )

    result_handler = WorkflowResultHandler(
        engine=engine,
        coordinator=coordinator,
    )

    bus.consume_agent_messages(
        queue_name="rkjo.workflow.results",
        callback=result_handler.handle,
    )

    coordinator.dispatch_next(
        execution,
        correlation_id="corr-capability-001",
    )

    assert len(
        bus.published_messages[
            "education.tutor.low.queue"
        ]
    ) == 0

    assert len(
        bus.published_messages[
            "education.tutor.high.queue"
        ]
    ) == 1

    dispatched = bus.published_messages[
        "education.tutor.high.queue"
    ][0]

    assert dispatched.target == "education.tutor.high"

    assert (
        dispatched.metadata["capability_name"]
        == "education.tutoring"
    )

    assert (
        dispatched.correlation_id
        == "corr-capability-001"
    )

    assert low_runtime.total_runtime_messages == 0
    assert high_runtime.total_runtime_messages == 1

    restored = repository.get(
        execution.execution_id
    )

    assert restored is not None
    assert restored.status == WorkflowStatus.COMPLETED

    assert restored.context.outputs["tutoring"] == {
        "lesson": "addition-with-carry",
        "explanation": "27 + 18 = 45",
    }
