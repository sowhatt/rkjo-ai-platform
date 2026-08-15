from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from rkjo_api.oidc_auth import (
    _build_jwks_client,
    decode_oidc_token,
    get_oidc_configuration,
    resolve_oidc_identity,
)
from rkjo_api.security import ApiRole


ISSUER = "https://identity.example.test"
AUDIENCE = "rkjo-api"
JWKS_URL = (
    "https://identity.example.test/"
    ".well-known/jwks.json"
)


@pytest.fixture
def rsa_keys():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    return (
        private_key,
        private_key.public_key(),
    )


@pytest.fixture
def oidc_environment(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_OIDC_ISSUER",
        ISSUER,
    )

    monkeypatch.setenv(
        "RKJO_OIDC_AUDIENCE",
        AUDIENCE,
    )

    monkeypatch.setenv(
        "RKJO_OIDC_JWKS_URL",
        JWKS_URL,
    )

    monkeypatch.setenv(
        "RKJO_OIDC_ALGORITHM",
        "RS256",
    )


def make_token(
    private_key,
    *,
    issuer=ISSUER,
    audience=AUDIENCE,
    role="viewer",
):
    now = datetime.now(
        timezone.utc
    )

    return jwt.encode(
        {
            "sub": "oidc-user-001",
            "role": role,
            "iss": issuer,
            "aud": audience,
            "iat": now,
            "exp": now + timedelta(
                minutes=5
            ),
        },
        private_key,
        algorithm="RS256",
        headers={
            "kid": "test-key-001"
        },
    )


def install_fake_jwks(
    monkeypatch,
    public_key,
):
    _build_jwks_client.cache_clear()

    class FakeSigningKey:
        key = public_key

    class FakePyJWKClient:
        def __init__(
            self,
            url,
            **kwargs,
        ):
            assert url == JWKS_URL

        def get_signing_key_from_jwt(
            self,
            token,
        ):
            return FakeSigningKey()

    monkeypatch.setattr(
        jwt,
        "PyJWKClient",
        FakePyJWKClient,
    )


def test_load_oidc_configuration(
    oidc_environment,
):
    config = get_oidc_configuration()

    assert config.issuer == ISSUER
    assert config.audience == AUDIENCE
    assert config.jwks_url == JWKS_URL
    assert config.algorithm == "RS256"


def test_valid_oidc_token_is_decoded(
    oidc_environment,
    rsa_keys,
    monkeypatch,
):
    private_key, public_key = (
        rsa_keys
    )

    install_fake_jwks(
        monkeypatch,
        public_key,
    )

    token = make_token(
        private_key
    )

    payload = decode_oidc_token(
        token
    )

    assert payload["sub"] == (
        "oidc-user-001"
    )

    assert payload["role"] == (
        "viewer"
    )


def test_oidc_identity_resolves_role(
    oidc_environment,
    rsa_keys,
    monkeypatch,
):
    private_key, public_key = (
        rsa_keys
    )

    install_fake_jwks(
        monkeypatch,
        public_key,
    )

    token = make_token(
        private_key,
        role="operator",
    )

    subject, role = (
        resolve_oidc_identity(
            token
        )
    )

    assert subject == "oidc-user-001"
    assert role == ApiRole.OPERATOR


def test_wrong_issuer_is_rejected(
    oidc_environment,
    rsa_keys,
    monkeypatch,
):
    private_key, public_key = (
        rsa_keys
    )

    install_fake_jwks(
        monkeypatch,
        public_key,
    )

    token = make_token(
        private_key,
        issuer=(
            "https://attacker.example"
        ),
    )

    with pytest.raises(
        jwt.InvalidIssuerError
    ):
        decode_oidc_token(
            token
        )


def test_wrong_audience_is_rejected(
    oidc_environment,
    rsa_keys,
    monkeypatch,
):
    private_key, public_key = (
        rsa_keys
    )

    install_fake_jwks(
        monkeypatch,
        public_key,
    )

    token = make_token(
        private_key,
        audience="other-api",
    )

    with pytest.raises(
        jwt.InvalidAudienceError
    ):
        decode_oidc_token(
            token
        )


def test_invalid_oidc_role_is_rejected(
    oidc_environment,
    rsa_keys,
    monkeypatch,
):
    private_key, public_key = (
        rsa_keys
    )

    install_fake_jwks(
        monkeypatch,
        public_key,
    )

    token = make_token(
        private_key,
        role="superuser",
    )

    with pytest.raises(
        ValueError,
        match="invalid role",
    ):
        resolve_oidc_identity(
            token
        )


def test_missing_oidc_configuration_fails(
    monkeypatch,
):
    for variable in (
        "RKJO_OIDC_ISSUER",
        "RKJO_OIDC_AUDIENCE",
        "RKJO_OIDC_JWKS_URL",
    ):
        monkeypatch.delenv(
            variable,
            raising=False,
        )

    with pytest.raises(
        RuntimeError,
        match="RKJO_OIDC_ISSUER",
    ):
        get_oidc_configuration()
