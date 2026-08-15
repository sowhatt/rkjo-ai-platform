import pytest
from fastapi.testclient import TestClient

from rkjo_api.dependencies import (
    get_workflow_repository,
)
from rkjo_api.main import app
from rkjo_api.security import (
    is_protected_path,
    verify_api_key,
)


class ReadyRepository:
    def initialize_schema(self):
        return None


@pytest.fixture
def client():
    def override_repository():
        return ReadyRepository()

    app.dependency_overrides[
        get_workflow_repository
    ] = override_repository

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(
        get_workflow_repository,
        None,
    )


def test_health_is_public(
    client,
):
    response = client.get(
        "/health"
    )

    assert response.status_code == 200


def test_ready_is_public(
    client,
):
    response = client.get(
        "/ready"
    )

    assert response.status_code == 200


def test_metrics_requires_api_key(
    client,
):
    response = client.get(
        "/metrics"
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": (
            "Invalid or missing API key."
        )
    }


def test_workflow_endpoint_requires_api_key(
    client,
):
    response = client.get(
        "/workflows/executions/unknown"
    )

    assert response.status_code == 401


def test_wrong_api_key_is_rejected(
    client,
):
    response = client.get(
        "/metrics",
        headers={
            "X-API-Key": "wrong-key"
        },
    )

    assert response.status_code == 401


def test_correct_api_key_is_accepted(
    client,
):
    response = client.get(
        "/metrics",
        headers={
            "X-API-Key": (
                "rkjo-test-api-key"
            )
        },
    )

    assert response.status_code == 200


def test_missing_server_configuration_fails_closed(
    client,
    monkeypatch,
):
    for variable in (
        "RKJO_API_KEY",
        "RKJO_VIEWER_API_KEY",
        "RKJO_OPERATOR_API_KEY",
        "RKJO_ADMIN_API_KEY",
    ):
        monkeypatch.delenv(
            variable,
            raising=False,
        )

    response = client.get(
        "/metrics",
        headers={
            "X-API-Key": "anything"
        },
    )

    assert response.status_code == 503

    assert response.json() == {
        "detail": (
            "API authentication "
            "is not configured."
        )
    }


def test_security_path_classification():
    assert is_protected_path(
        "/metrics"
    )

    assert is_protected_path(
        "/workflows/executions/123"
    )

    assert not is_protected_path(
        "/health"
    )

    assert not is_protected_path(
        "/ready"
    )


def test_verify_api_key(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_API_KEY",
        "secret-001",
    )

    assert verify_api_key(
        "secret-001"
    )

    assert not verify_api_key(
        "secret-002"
    )

    assert not verify_api_key(
        None
    )
