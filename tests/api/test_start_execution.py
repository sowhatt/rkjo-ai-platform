
import pytest
from fastapi.testclient import TestClient

from rkjo_api.dependencies import (
    get_async_dispatcher,
    get_workflow_agent_router,
    get_workflow_engine,
    get_workflow_uow_factory,
)
from rkjo_api.main import app
from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.workflow.agent_routing import WorkflowAgentRouter
from rkjo_kernel.workflow.async_dispatch import (
    AsyncWorkflowDispatcher,
)
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.in_memory_unit_of_work import (
    InMemoryWorkflowUnitOfWork,
)
from rkjo_kernel.workflow.models.workflow_definition import (
    WorkflowDefinition,
)
from rkjo_kernel.workflow.models.workflow_step import (
    WorkflowStep,
)


class FakeEventBus(EventBus):
    def __init__(self):
        self.messages = []

    def publish(
        self,
        queue_name,
        message,
    ):
        pass

    def consume(
        self,
        queue_name,
        callback,
    ):
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


@pytest.fixture
def uow():
    return InMemoryWorkflowUnitOfWork()


@pytest.fixture
def repository(uow):
    return uow.workflows


@pytest.fixture
def event_bus():
    return FakeEventBus()


@pytest.fixture
def engine(repository):
    return WorkflowEngine(
        repository=repository
    )


@pytest.fixture
def router():
    registry = AgentRegistry()

    service = RegistryService(
        registry=registry
    )

    service.register_agent(
        AgentDescriptor(
            name="weather.agent",
            display_name="Weather Agent",
            product="ADIP",
            queue_name="weather.queue",
            status=AgentStatus.AVAILABLE,
            capabilities=[
                AgentCapability(
                    name="platform_task",
                    description="Generic platform task",
                    input_schema={},
                    output_schema={},
                )
            ],
        )
    )

    return WorkflowAgentRouter(
        registry_service=service
    )


@pytest.fixture
def client(
    engine,
    event_bus,
    router,
    uow,
):
    def override_engine():
        return engine

    def override_dispatcher():
        return AsyncWorkflowDispatcher(
            event_bus=event_bus
        )

    def override_router():
        return router

    def override_uow_factory():
        return lambda: uow

    app.dependency_overrides[
        get_workflow_engine
    ] = override_engine

    app.dependency_overrides[
        get_async_dispatcher
    ] = override_dispatcher

    app.dependency_overrides[
        get_workflow_agent_router
    ] = override_router

    app.dependency_overrides[
        get_workflow_uow_factory
    ] = override_uow_factory

    with TestClient(
        app,
        headers={
            "X-API-Key": "rkjo-test-api-key"
        },
    ) as test_client:
        yield test_client

    app.dependency_overrides.pop(
        get_workflow_engine,
        None,
    )

    app.dependency_overrides.pop(
        get_async_dispatcher,
        None,
    )

    app.dependency_overrides.pop(
        get_workflow_agent_router,
        None,
    )

    app.dependency_overrides.pop(
        get_workflow_uow_factory,
        None,
    )


def create_execution(
    engine,
):
    definition = WorkflowDefinition(
        workflow_id="start-api-workflow",
        name="Start API Workflow",
        steps=[
            WorkflowStep(
                step_id="weather",
                name="Weather",
                agent_name="weather.agent",
            )
        ],
    )

    return engine.create_execution(
        definition,
        execution_id="start-api-001",
    )


def test_start_execution_enqueues_first_step_without_direct_publish(
    client,
    engine,
    event_bus,
    uow,
):
    create_execution(
        engine
    )

    response = client.post(
        "/workflows/executions/start-api-001/start"
    )

    assert response.status_code == 202

    payload = response.json()

    assert payload["execution_id"] == (
        "start-api-001"
    )

    assert payload["workflow_id"] == (
        "start-api-workflow"
    )

    assert payload["status"] == "running"

    assert payload["step_id"] == "weather"

    assert payload["queue_name"] == (
        "weather.queue"
    )

    assert payload["message_id"]

    assert payload["correlation_id"]

    # The API must never publish directly to RabbitMQ. The durable outbox
    # publisher owns external delivery after the database transaction commits.
    assert event_bus.messages == []

    pending = uow.outbox.pending()
    assert len(pending) == 1

    outbox_message = pending[0]
    assert outbox_message.outbox_id == payload["message_id"]
    assert outbox_message.queue_name == "weather.queue"
    assert outbox_message.message.target == "weather.agent"
    assert outbox_message.message.message_type == "workflow.step.execute"
    assert outbox_message.message.metadata[
        "workflow_execution_id"
    ] == "start-api-001"
    assert outbox_message.message.metadata[
        "workflow_step_id"
    ] == "weather"
    assert outbox_message.message.metadata[
        "reply_queue"
    ] == "rkjo.workflow.results"


def test_start_capability_routed_execution_targets_resolved_agent(
    client,
    engine,
    uow,
):
    definition = WorkflowDefinition(
        workflow_id="capability-start-api",
        name="Capability Start API",
        steps=[
            WorkflowStep(
                step_id="platform",
                name="Platform Task",
                capability_name="platform_task",
            )
        ],
    )

    engine.create_execution(
        definition,
        execution_id="capability-start-api-001",
    )

    response = client.post(
        "/workflows/executions/capability-start-api-001/start"
    )

    assert response.status_code == 202

    pending = uow.outbox.pending()
    assert len(pending) == 1
    assert pending[0].queue_name == "weather.queue"
    assert pending[0].message.target == "weather.agent"
    assert pending[0].message.metadata[
        "capability_name"
    ] == "platform_task"


def test_start_unknown_execution_returns_404(
    client,
):
    response = client.post(
        "/workflows/executions/unknown/start"
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Workflow execution not found."
    }


def test_execution_and_outbox_are_committed_together(
    client,
    engine,
    repository,
    uow,
):
    create_execution(
        engine
    )

    response = client.post(
        "/workflows/executions/start-api-001/start"
    )

    assert response.status_code == 202

    stored = repository.get(
        "start-api-001"
    )

    assert stored is not None
    assert stored.status.value == "running"
    assert stored.current_step_id == "weather"

    pending = uow.outbox.pending()
    assert len(pending) == 1
    assert pending[0].message.metadata[
        "workflow_execution_id"
    ] == stored.execution_id


def test_start_execution_twice_returns_conflict(
    client,
    engine,
):
    create_execution(
        engine
    )

    first = client.post(
        "/workflows/executions/start-api-001/start"
    )

    assert first.status_code == 202

    second = client.post(
        "/workflows/executions/start-api-001/start"
    )

    assert second.status_code in (
        409,
        422,
    )
