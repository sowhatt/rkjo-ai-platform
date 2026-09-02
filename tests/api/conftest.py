from fastapi.testclient import TestClient
from rkjo_api.main import app

import pytest


@pytest.fixture(autouse=True)
def configured_api_keys(
    monkeypatch,
):
    # Legacy key remains admin-compatible.
    monkeypatch.setenv(
        "RKJO_API_KEY",
        "rkjo-test-api-key",
    )

    monkeypatch.setenv(
        "RKJO_VIEWER_API_KEY",
        "rkjo-viewer-key",
    )

    monkeypatch.setenv(
        "RKJO_OPERATOR_API_KEY",
        "rkjo-operator-key",
    )

    monkeypatch.setenv(
        "RKJO_ADMIN_API_KEY",
        "rkjo-admin-key",
    )

    # RAG API tests are tenant-scoped. Keep all role-specific
    # credentials bound to the same deterministic tenant unless
    # an individual test overrides the environment explicitly.
    monkeypatch.setenv(
        "RKJO_API_TENANT_ID",
        "tenant-a",
    )

    monkeypatch.setenv(
        "RKJO_VIEWER_TENANT_ID",
        "tenant-a",
    )

    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        "tenant-a",
    )

    monkeypatch.setenv(
        "RKJO_ADMIN_TENANT_ID",
        "tenant-a",
    )

    monkeypatch.setenv(
        "RKJO_JWT_SECRET",
        "rkjo-test-jwt-secret-with-sufficient-length-123456",
    )

    # Some invalid-payload tests intentionally exercise FastAPI
    # validation without overriding the production RAG dependency.
    # A deterministic dummy key prevents dependency construction from
    # failing before request validation can return the expected 422.
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "rkjo-test-openai-key",
    )


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def viewer_headers():
    return {
        "X-API-Key": "rkjo-viewer-key"
    }
