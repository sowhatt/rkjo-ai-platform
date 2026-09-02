from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.workflow.agent_routing import WorkflowAgentRouter
from rkjo_kernel.workflow.async_coordinator import AsyncWorkflowCoordinator
from rkjo_kernel.workflow.async_dispatch import AsyncWorkflowDispatcher
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.models.workflow_definition import WorkflowDefinition
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep
from rkjo_kernel.workflow.repository.memory import InMemoryWorkflowRepository


class FakeEventBus(EventBus):
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


def make_coordinator():
    repository = InMemoryWorkflowRepository()
    engine = WorkflowEngine(repository=repository)

    registry = AgentRegistry()
    service = RegistryService(registry=registry)

    service.register_agent(
        AgentDescriptor(
            name="diagnostic.agent",
            display_name="Diagnostic Agent",
            product="RKJO Education",
            queue_name="education.diagnostic",
            status=AgentStatus.AVAILABLE,
        )
    )

    service.register_agent(
        AgentDescriptor(
            name="tutor.agent",
            display_name="Tutor Agent",
            product="RKJO Education",
            queue_name="education.tutor",
            status=AgentStatus.AVAILABLE,
        )
    )

    router = WorkflowAgentRouter(
        registry_service=service
    )

    bus = FakeEventBus()

    coordinator = AsyncWorkflowCoordinator(
        engine=engine,
        router=router,
        dispatcher=AsyncWorkflowDispatcher(
            event_bus=bus
        ),
        reply_queue="rkjo.workflow.results",
    )

    return engine, coordinator, bus


def make_execution(engine):
    definition = WorkflowDefinition(
        workflow_id="education-learning",
        name="Education Learning Workflow",
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
        execution_id="education-001",
        input_data={
            "student_id": "student-001",
        },
    )

    engine.start(execution)

    return execution


def test_dispatch_next_starts_and_publishes_first_step():
    engine, coordinator, bus = make_coordinator()
    execution = make_execution(engine)

    result = coordinator.dispatch_next(
        execution,
        correlation_id="corr-education",
    )

    assert result is not None
    assert result.step_id == "diagnostic"
    assert execution.current_step_id == "diagnostic"

    assert len(bus.published) == 1

    queue_name, message = bus.published[0]

    assert queue_name == "education.diagnostic"
    assert message.message_type == "workflow.step.execute"
    assert message.correlation_id == "corr-education"
    assert message.metadata[
        "workflow_execution_id"
    ] == "education-001"
    assert message.metadata[
        "workflow_step_id"
    ] == "diagnostic"
    assert message.metadata[
        "reply_queue"
    ] == "rkjo.workflow.results"


def test_dispatch_next_returns_none_when_no_step_remains():
    engine, coordinator, bus = make_coordinator()
    execution = make_execution(engine)

    coordinator.dispatch_next(execution)

    engine.complete_current_step(
        execution,
        output={"level": "beginner"},
    )

    coordinator.dispatch_next(execution)

    engine.complete_current_step(
        execution,
        output={"lesson": "fractions"},
    )

    result = coordinator.dispatch_next(execution)

    assert result is None
    assert len(bus.published) == 2


def test_prepare_next_starts_and_prepares_without_publishing():
    engine, coordinator, bus = make_coordinator()
    execution = make_execution(engine)

    prepared = coordinator.prepare_next(
        execution,
        correlation_id="corr-prepare-001",
    )

    assert prepared is not None
    assert prepared.step_id == "diagnostic"
    assert prepared.queue_name == "education.diagnostic"

    assert prepared.message.target == "diagnostic.agent"
    assert (
        prepared.message.correlation_id
        == "corr-prepare-001"
    )
    assert (
        prepared.message.message_type
        == "workflow.step.execute"
    )

    assert prepared.message.metadata[
        "workflow_execution_id"
    ] == "education-001"

    assert prepared.message.metadata[
        "workflow_step_id"
    ] == "diagnostic"

    assert prepared.message.metadata[
        "reply_queue"
    ] == "rkjo.workflow.results"

    assert execution.current_step_id == "diagnostic"

    # prepare_next() must not publish externally.
    assert bus.published == []


def test_prepare_next_returns_none_when_no_step_remains():
    engine, coordinator, bus = make_coordinator()
    execution = make_execution(engine)

    first = coordinator.prepare_next(execution)

    assert first is not None
    assert first.step_id == "diagnostic"

    engine.complete_current_step(
        execution,
        output={"level": "beginner"},
    )

    second = coordinator.prepare_next(execution)

    assert second is not None
    assert second.step_id == "tutoring"

    engine.complete_current_step(
        execution,
        output={"lesson": "fractions"},
    )

    prepared = coordinator.prepare_next(execution)

    assert prepared is None

    # No prepared message has been published to EventBus.
    assert bus.published == []
