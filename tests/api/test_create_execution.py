
import pytest
from fastapi.testclient import TestClient

from rkjo_api.dependencies import get_workflow_engine
from rkjo_api.main import app
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.repository.memory import (
    InMemoryWorkflowRepository,
)


@pytest.fixture
def repository():
    return InMemoryWorkflowRepository()


@pytest.fixture
def client(repository):
    def override_engine():
        return WorkflowEngine(
            repository=repository
        )

    app.dependency_overrides[
        get_workflow_engine
    ] = override_engine

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


def test_create_execution(
    client,
    repository,
):
    response = client.post(
        "/workflows/executions",
        json={
            "workflow_id": "api-create",
            "name": "API Create Workflow",
            "execution_id": "api-create-001",
            "input_data": {
                "parcel_id": "P-100",
            },
            "metadata": {
                "product": "ADIP",
            },
            "steps": [
                {
                    "step_id": "weather",
                    "name": "Weather Analysis",
                    "capability_name": "weather.analysis",
                    "position": 0,
                }
            ],
        },
    )

    assert response.status_code == 201

    payload = response.json()

    assert payload["execution_id"] == (
        "api-create-001"
    )

    assert payload["workflow_id"] == (
        "api-create"
    )

    assert payload["status"] == "pending"
    assert payload["progress"] == 0.0

    stored = repository.get(
        "api-create-001"
    )

    assert stored is not None

    assert stored.context.input_data == {
        "parcel_id": "P-100"
    }

    assert stored.metadata == {
        "product": "ADIP"
    }


def test_create_capability_routed_execution(
    client,
    repository,
):
    response = client.post(
        "/workflows/executions",
        json={
            "workflow_id": "capability-api",
            "name": "Capability API Workflow",
            "execution_id": "api-capability-001",
            "steps": [
                {
                    "step_id": "risk",
                    "name": "Risk Analysis",
                    "capability_name": "risk.analysis",
                }
            ],
        },
    )

    assert response.status_code == 201

    stored = repository.get(
        "api-capability-001"
    )

    assert stored is not None

    assert (
        stored.definition.steps[0]
        .capability_name
        == "risk.analysis"
    )


def test_create_agent_routed_execution(
    client,
    repository,
):
    response = client.post(
        "/workflows/executions",
        json={
            "workflow_id": "agent-api",
            "name": "Agent API Workflow",
            "execution_id": "api-agent-001",
            "steps": [
                {
                    "step_id": "weather",
                    "name": "Weather",
                    "agent_name": "weather.agent",
                }
            ],
        },
    )

    assert response.status_code == 201

    stored = repository.get(
        "api-agent-001"
    )

    assert stored is not None

    assert (
        stored.definition.steps[0]
        .agent_name
        == "weather.agent"
    )


def test_invalid_step_routing_returns_422(
    client,
):
    response = client.post(
        "/workflows/executions",
        json={
            "workflow_id": "invalid-api",
            "name": "Invalid Workflow",
            "steps": [
                {
                    "step_id": "invalid",
                    "name": "Invalid",
                }
            ],
        },
    )

    assert response.status_code == 422
