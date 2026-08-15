from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from rkjo_api.jwt_auth import (
    JWT_ALGORITHM,
    create_access_token,
    decode_access_token,
    resolve_jwt_role,
)
from rkjo_api.main import app
from rkjo_api.security import ApiRole


def test_create_and_decode_token():
    token = create_access_token(
        subject="user-001",
        role=ApiRole.VIEWER,
    )

    payload = decode_access_token(
        token
    )

    assert payload["sub"] == "user-001"
    assert payload["role"] == "viewer"


def test_resolve_jwt_role():
    token = create_access_token(
        subject="operator-001",
        role=ApiRole.OPERATOR,
    )

    subject, role = resolve_jwt_role(
        token
    )

    assert subject == "operator-001"
    assert role == ApiRole.OPERATOR


def test_empty_subject_is_rejected():
    with pytest.raises(
        ValueError,
        match="subject",
    ):
        create_access_token(
            subject=" ",
            role=ApiRole.VIEWER,
        )


def test_expired_token_is_rejected(
    monkeypatch,
):
    secret = (
        "rkjo-test-jwt-secret-with-"
        "sufficient-length-123456"
    )

    monkeypatch.setenv(
        "RKJO_JWT_SECRET",
        secret,
    )

    now = datetime.now(
        timezone.utc
    )

    token = jwt.encode(
        {
            "sub": "expired-user",
            "role": "viewer",
            "iat": now - timedelta(
                minutes=10
            ),
            "exp": now - timedelta(
                minutes=5
            ),
        },
        secret,
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(
        jwt.ExpiredSignatureError
    ):
        decode_access_token(
            token
        )


def test_invalid_role_is_rejected():
    secret = (
        "rkjo-test-jwt-secret-with-"
        "sufficient-length-123456"
    )

    now = datetime.now(
        timezone.utc
    )

    token = jwt.encode(
        {
            "sub": "user-001",
            "role": "superuser",
            "iat": now,
            "exp": now + timedelta(
                minutes=5
            ),
        },
        secret,
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(
        ValueError,
        match="invalid role",
    ):
        resolve_jwt_role(
            token
        )


def test_viewer_jwt_can_read_metrics():
    token = create_access_token(
        subject="viewer-001",
        role=ApiRole.VIEWER,
    )

    client = TestClient(app)

    response = client.get(
        "/metrics",
        headers={
            "Authorization": (
                f"Bearer {token}"
            )
        },
    )

    assert response.status_code == 200


def test_viewer_jwt_cannot_create_workflow():
    token = create_access_token(
        subject="viewer-001",
        role=ApiRole.VIEWER,
    )

    client = TestClient(app)

    response = client.post(
        "/workflows/executions",
        json={
            "workflow_id": "jwt-rbac",
            "name": "JWT RBAC",
            "steps": [
                {
                    "step_id": "weather",
                    "name": "Weather",
                    "agent_name": "weather.agent",
                }
            ],
        },
        headers={
            "Authorization": (
                f"Bearer {token}"
            )
        },
    )

    assert response.status_code == 403


def test_operator_jwt_reaches_workflow_endpoint():
    token = create_access_token(
        subject="operator-001",
        role=ApiRole.OPERATOR,
    )

    client = TestClient(app)

    response = client.post(
        "/workflows/executions",
        json={
            "workflow_id": "jwt-operator",
            "name": "JWT Operator",
            "execution_id": "jwt-op-001",
            "steps": [
                {
                    "step_id": "weather",
                    "name": "Weather",
                    "agent_name": "weather.agent",
                }
            ],
        },
        headers={
            "Authorization": (
                f"Bearer {token}"
            )
        },
    )

    # Auth/RBAC succeeded.
    # Endpoint may still depend on the real repository.
    assert response.status_code != 401
    assert response.status_code != 403


def test_invalid_jwt_returns_401():
    client = TestClient(app)

    response = client.get(
        "/metrics",
        headers={
            "Authorization": (
                "Bearer definitely-invalid"
            )
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Invalid or expired JWT."
    }


def test_api_key_fallback_still_works():
    client = TestClient(app)

    response = client.get(
        "/metrics",
        headers={
            "X-API-Key": "rkjo-viewer-key"
        },
    )

    assert response.status_code == 200
