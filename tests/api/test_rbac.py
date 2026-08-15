import pytest
from fastapi.testclient import TestClient

from rkjo_api.dependencies import (
    get_workflow_engine,
)
from rkjo_api.main import app
from rkjo_api.security import (
    ApiRole,
    required_role_for_request,
    resolve_api_role,
    role_allows,
)
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

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(
        get_workflow_engine,
        None,
    )


def workflow_payload():
    return {
        "workflow_id": "rbac-workflow",
        "name": "RBAC Workflow",
        "execution_id": "rbac-exec-001",
        "steps": [
            {
                "step_id": "weather",
                "name": "Weather",
                "agent_name": "weather.agent",
            }
        ],
    }


def test_viewer_can_read_metrics(
    client,
):
    response = client.get(
        "/metrics",
        headers={
            "X-API-Key": "rkjo-viewer-key"
        },
    )

    assert response.status_code == 200


def test_viewer_cannot_create_workflow(
    client,
):
    response = client.post(
        "/workflows/executions",
        json=workflow_payload(),
        headers={
            "X-API-Key": "rkjo-viewer-key"
        },
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": "Insufficient permissions."
    }


def test_operator_can_create_workflow(
    client,
):
    response = client.post(
        "/workflows/executions",
        json=workflow_payload(),
        headers={
            "X-API-Key": "rkjo-operator-key"
        },
    )

    assert response.status_code == 201


def test_admin_can_create_workflow(
    client,
):
    payload = workflow_payload()

    payload[
        "execution_id"
    ] = "rbac-admin-001"

    response = client.post(
        "/workflows/executions",
        json=payload,
        headers={
            "X-API-Key": "rkjo-admin-key"
        },
    )

    assert response.status_code == 201


def test_legacy_api_key_has_admin_permissions(
    client,
):
    payload = workflow_payload()

    payload[
        "execution_id"
    ] = "rbac-legacy-001"

    response = client.post(
        "/workflows/executions",
        json=payload,
        headers={
            "X-API-Key": "rkjo-test-api-key"
        },
    )

    assert response.status_code == 201


def test_role_resolution(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_VIEWER_API_KEY",
        "viewer-secret",
    )

    assert resolve_api_role(
        "viewer-secret"
    ) == ApiRole.VIEWER


def test_role_hierarchy():
    assert role_allows(
        actual_role=ApiRole.ADMIN,
        required_role=ApiRole.VIEWER,
    )

    assert role_allows(
        actual_role=ApiRole.OPERATOR,
        required_role=ApiRole.VIEWER,
    )

    assert not role_allows(
        actual_role=ApiRole.VIEWER,
        required_role=ApiRole.OPERATOR,
    )


def test_get_workflow_requires_viewer():
    role = required_role_for_request(
        method="GET",
        path="/workflows/executions/abc",
    )

    assert role == ApiRole.VIEWER


def test_post_workflow_requires_operator():
    role = required_role_for_request(
        method="POST",
        path="/workflows/executions",
    )

    assert role == ApiRole.OPERATOR


def test_delete_workflow_requires_admin():
    role = required_role_for_request(
        method="DELETE",
        path="/workflows/executions/abc",
    )

    assert role == ApiRole.ADMIN
