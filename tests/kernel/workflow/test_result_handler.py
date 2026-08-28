from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.models.workflow_definition import (
    WorkflowDefinition,
)
from rkjo_kernel.workflow.models.workflow_status import (
    WorkflowStatus,
)
from rkjo_kernel.workflow.models.workflow_step import (
    WorkflowStep,
)
from rkjo_kernel.workflow.repository.memory import (
    InMemoryWorkflowRepository,
)
from rkjo_kernel.workflow.result_handler import (
    WorkflowResultHandler,
)


def make_engine():
    repository = InMemoryWorkflowRepository()

    engine = WorkflowEngine(
        repository=repository
    )

    definition = WorkflowDefinition(
        workflow_id="workflow-result",
        name="Result Workflow",
        steps=[
            WorkflowStep(
                step_id="weather",
                name="Weather",
                capability_name="weather.analysis",
            )
        ],
    )

    execution = engine.create_execution(
        definition,
        execution_id="exec-001",
    )

    engine.start(execution)
    engine.start_next_step(execution)

    return engine, repository


def test_success_result_completes_step_and_workflow():
    engine, repository = make_engine()

    handler = WorkflowResultHandler(
        engine=engine
    )

    message = AgentMessage(
        source="weather.agent",
        target="rkjo.workflow",
        message_type="workflow.step.result",
        correlation_id="corr-001",
        payload={
            "success": True,
            "result": {
                "temperature": 31,
            },
        },
        metadata={
            "workflow_execution_id": "exec-001",
            "workflow_step_id": "weather",
        },
    )

    handler.handle(message)

    execution = repository.get(
        "exec-001"
    )

    assert execution is not None
    assert execution.status == (
        WorkflowStatus.COMPLETED
    )

    assert execution.context.outputs == {
        "weather": {
            "temperature": 31,
        }
    }


def test_failure_result_fails_workflow():
    engine, repository = make_engine()

    handler = WorkflowResultHandler(
        engine=engine
    )

    message = AgentMessage(
        source="weather.agent",
        target="rkjo.workflow",
        message_type="workflow.step.result",
        payload={
            "success": False,
            "error": "weather provider unavailable",
        },
        metadata={
            "workflow_execution_id": "exec-001",
            "workflow_step_id": "weather",
        },
    )

    handler.handle(message)

    execution = repository.get(
        "exec-001"
    )

    assert execution is not None
    assert execution.status == (
        WorkflowStatus.FAILED
    )

    assert execution.error == (
        "weather provider unavailable"
    )


def test_success_result_dispatches_next_step_with_coordinator():
    from rkjo_kernel.events.event_bus import EventBus
    from rkjo_kernel.registry.descriptor import (
        AgentDescriptor,
        AgentStatus,
    )
    from rkjo_kernel.registry.registry import AgentRegistry
    from rkjo_kernel.services.registry_service import RegistryService
    from rkjo_kernel.workflow.agent_routing import WorkflowAgentRouter
    from rkjo_kernel.workflow.async_coordinator import AsyncWorkflowCoordinator
    from rkjo_kernel.workflow.async_dispatch import AsyncWorkflowDispatcher

    class FakeBus(EventBus):
        def __init__(self):
            self.published = []

        def publish(self, queue_name, message):
            pass

        def consume(self, queue_name, callback):
            pass

        def publish_agent_message(self, queue_name, message):
            self.published.append((queue_name, message))

        def consume_agent_messages(self, queue_name, callback):
            pass

        def close(self):
            pass

    repository = InMemoryWorkflowRepository()
    engine = WorkflowEngine(repository=repository)

    definition = WorkflowDefinition(
        workflow_id="education-result",
        name="Education Result Workflow",
        steps=[
            WorkflowStep(
                step_id="diagnostic",
                name="Diagnostic",
                agent_name="diagnostic.agent",
                position=0,
            ),
            WorkflowStep(
                step_id="tutoring",
                name="Tutoring",
                agent_name="tutor.agent",
                position=1,
            ),
        ],
    )

    execution = engine.create_execution(
        definition,
        execution_id="education-result-001",
    )

    engine.start(execution)
    engine.start_next_step(execution)

    registry = AgentRegistry()
    service = RegistryService(registry=registry)

    service.register_agent(
        AgentDescriptor(
            name="tutor.agent",
            display_name="Tutor Agent",
            product="RKJO Education",
            queue_name="education.tutor",
            status=AgentStatus.AVAILABLE,
        )
    )

    bus = FakeBus()

    coordinator = AsyncWorkflowCoordinator(
        engine=engine,
        router=WorkflowAgentRouter(
            registry_service=service
        ),
        dispatcher=AsyncWorkflowDispatcher(
            event_bus=bus
        ),
        reply_queue="rkjo.workflow.results",
    )

    handler = WorkflowResultHandler(
        engine=engine,
        coordinator=coordinator,
    )

    message = AgentMessage(
        source="diagnostic.agent",
        target="rkjo.workflow",
        message_type="workflow.step.result",
        correlation_id="corr-education",
        payload={
            "success": True,
            "result": {
                "level": "beginner",
            },
        },
        metadata={
            "workflow_execution_id": (
                "education-result-001"
            ),
            "workflow_step_id": "diagnostic",
        },
    )

    handler.handle(message)

    restored = repository.get(
        "education-result-001"
    )

    assert restored is not None
    assert restored.current_step_id == "tutoring"

    assert restored.context.outputs[
        "diagnostic"
    ] == {
        "level": "beginner",
    }

    assert len(bus.published) == 1

    queue_name, dispatched = bus.published[0]

    assert queue_name == "education.tutor"
    assert dispatched.metadata[
        "workflow_step_id"
    ] == "tutoring"

    assert dispatched.payload[
        "outputs"
    ] == {
        "diagnostic": {
            "level": "beginner",
        }
    }
