import pytest

from rkjo_api.bearer_auth import (
    oidc_is_configured,
    resolve_bearer_identity,
)
from rkjo_api.jwt_auth import (
    create_access_token,
)
from rkjo_api.security import ApiRole


def test_local_jwt_still_resolves():
    token = create_access_token(
        subject="local-user",
        role=ApiRole.ADMIN,
    )

    subject, role = (
        resolve_bearer_identity(
            token
        )
    )

    assert subject == "local-user"
    assert role == ApiRole.ADMIN


def test_oidc_configuration_detection(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_OIDC_ISSUER",
        "https://issuer.test",
    )
    monkeypatch.setenv(
        "RKJO_OIDC_AUDIENCE",
        "rkjo-api",
    )
    monkeypatch.setenv(
        "RKJO_OIDC_JWKS_URL",
        "https://issuer.test/jwks",
    )

    assert oidc_is_configured()


def test_partial_oidc_configuration_is_not_enabled(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_OIDC_ISSUER",
        "https://issuer.test",
    )

    monkeypatch.delenv(
        "RKJO_OIDC_AUDIENCE",
        raising=False,
    )

    monkeypatch.delenv(
        "RKJO_OIDC_JWKS_URL",
        raising=False,
    )

    assert not oidc_is_configured()
