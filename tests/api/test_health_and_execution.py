
import pytest
from fastapi.testclient import TestClient

from rkjo_api.dependencies import (
    get_workflow_engine,
    get_workflow_repository,
)
from rkjo_api.main import app
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


def make_engine():
    repository = InMemoryWorkflowRepository()

    engine = WorkflowEngine(
        repository=repository
    )

    definition = WorkflowDefinition(
        workflow_id="api-workflow",
        name="API Workflow",
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
        execution_id="api-exec-001",
    )

    engine.start(execution)

    return engine


class ReadyRepository:
    def initialize_schema(self):
        return None


@pytest.fixture
def client():
    def override_engine():
        return make_engine()

    def override_repository():
        return ReadyRepository()

    app.dependency_overrides[
        get_workflow_engine
    ] = override_engine

    app.dependency_overrides[
        get_workflow_repository
    ] = override_repository

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
        get_workflow_repository,
        None,
    )


def test_health(client):
    response = client.get(
        "/health"
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "alive"
    }


def test_ready(client):
    response = client.get(
        "/ready"
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "ready"
    }


def test_get_execution(client):
    response = client.get(
        "/workflows/executions/api-exec-001"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload[
        "execution_id"
    ] == "api-exec-001"

    assert payload[
        "workflow_id"
    ] == "api-workflow"

    assert payload[
        "status"
    ] == "running"

    assert payload[
        "progress"
    ] == 0.0


def test_get_unknown_execution_returns_404(
    client,
):
    response = client.get(
        "/workflows/executions/unknown"
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Workflow execution not found."
    }
