from rkjo_api.jwt_auth import (
    create_access_token,
    resolve_jwt_identity,
)
from rkjo_api.security import ApiRole


def test_jwt_can_carry_tenant(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_JWT_SECRET",
        "test-secret-at-least-32-bytes-long",
    )

    token = create_access_token(
        subject="user-1",
        role=ApiRole.VIEWER,
        tenant_id="tenant-a",
    )

    subject, role, tenant_id = (
        resolve_jwt_identity(token)
    )

    assert subject == "user-1"
    assert role == ApiRole.VIEWER
    assert tenant_id == "tenant-a"


def test_jwt_without_tenant_remains_supported(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_JWT_SECRET",
        "test-secret-at-least-32-bytes-long",
    )

    token = create_access_token(
        subject="user-1",
        role=ApiRole.VIEWER,
    )

    _, _, tenant_id = (
        resolve_jwt_identity(token)
    )

    assert tenant_id is None
