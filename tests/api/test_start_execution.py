
import pytest
from fastapi.testclient import TestClient

from rkjo_api.dependencies import (
    get_async_dispatcher,
    get_workflow_engine,
)
from rkjo_api.main import app
from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.workflow.async_dispatch import (
    AsyncWorkflowDispatcher,
)
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.models.workflow_definition import (
    WorkflowDefinition,
)
from rkjo_kernel.workflow.models.workflow_step import (
    WorkflowStep,
)
from rkjo_kernel.workflow.repository.memory import (
    InMemoryWorkflowRepository,
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
def repository():
    return InMemoryWorkflowRepository()


@pytest.fixture
def event_bus():
    return FakeEventBus()


@pytest.fixture
def engine(repository):
    return WorkflowEngine(
        repository=repository
    )


@pytest.fixture
def client(
    engine,
    event_bus,
):
    def override_engine():
        return engine

    def override_dispatcher():
        return AsyncWorkflowDispatcher(
            event_bus=event_bus
        )

    app.dependency_overrides[
        get_workflow_engine
    ] = override_engine

    app.dependency_overrides[
        get_async_dispatcher
    ] = override_dispatcher

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(
        get_workflow_engine,
        None,
    )

    app.dependency_overrides.pop(
        get_async_dispatcher,
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
                agent_name="weather.queue",
            )
        ],
    )

    return engine.create_execution(
        definition,
        execution_id="start-api-001",
    )


def test_start_execution_dispatches_first_step(
    client,
    engine,
    event_bus,
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

    assert len(event_bus.messages) == 1

    queue_name, message = (
        event_bus.messages[0]
    )

    assert queue_name == "weather.queue"

    assert message.target == (
        "weather.queue"
    )

    assert message.message_type == (
        "workflow.step.execute"
    )

    assert message.metadata[
        "workflow_execution_id"
    ] == "start-api-001"

    assert message.metadata[
        "workflow_step_id"
    ] == "weather"

    assert message.metadata[
        "reply_queue"
    ] == "rkjo.workflow.results"


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


def test_execution_is_persisted_as_running(
    client,
    engine,
    repository,
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

    assert stored.current_step_id == (
        "weather"
    )


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
