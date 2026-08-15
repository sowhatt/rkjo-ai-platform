from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from rkjo_api.oidc_auth import (
    OIDCConfiguration,
    clear_jwks_client_cache,
    decode_oidc_token,
    get_jwks_client,
    get_oidc_configuration,
)


ISSUER = "https://identity.example.test"
AUDIENCE = "rkjo-api"
JWKS_URL = (
    "https://identity.example.test/"
    ".well-known/jwks.json"
)


@pytest.fixture(autouse=True)
def clear_cache():
    clear_jwks_client_cache()
    yield
    clear_jwks_client_cache()


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
    monkeypatch.setenv(
        "RKJO_OIDC_JWKS_TIMEOUT_SECONDS",
        "2.5",
    )
    monkeypatch.setenv(
        "RKJO_OIDC_JWKS_CACHE_LIFESPAN_SECONDS",
        "120",
    )
    monkeypatch.setenv(
        "RKJO_OIDC_JWKS_MAX_CACHED_KEYS",
        "8",
    )


def make_token(
    private_key,
    *,
    kid="kid-001",
):
    now = datetime.now(
        timezone.utc
    )

    return jwt.encode(
        {
            "sub": "oidc-user",
            "role": "viewer",
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": now,
            "exp": now + timedelta(
                minutes=5
            ),
        },
        private_key,
        algorithm="RS256",
        headers={
            "kid": kid
        },
    )


def test_hardening_configuration_values(
    oidc_environment,
):
    config = get_oidc_configuration()

    assert config.jwks_timeout_seconds == 2.5
    assert (
        config.jwks_cache_lifespan_seconds
        == 120.0
    )
    assert config.jwks_max_cached_keys == 8


def test_jwks_client_is_cached(
    oidc_environment,
    monkeypatch,
):
    created = []

    class FakeClient:
        def __init__(
            self,
            url,
            **kwargs,
        ):
            created.append(
                (url, kwargs)
            )

    monkeypatch.setattr(
        jwt,
        "PyJWKClient",
        FakeClient,
    )

    config = get_oidc_configuration()

    first = get_jwks_client(
        config
    )

    second = get_jwks_client(
        config
    )

    assert first is second
    assert len(created) == 1

    url, kwargs = created[0]

    assert url == JWKS_URL
    assert kwargs["cache_keys"] is True
    assert kwargs["cache_jwk_set"] is True
    assert kwargs["timeout"] == 2.5
    assert kwargs["lifespan"] == 120.0
    assert kwargs["max_cached_keys"] == 8


def test_missing_kid_is_rejected(
    oidc_environment,
):
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    now = datetime.now(
        timezone.utc
    )

    token = jwt.encode(
        {
            "sub": "user",
            "role": "viewer",
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": now,
            "exp": now + timedelta(
                minutes=5
            ),
        },
        private_key,
        algorithm="RS256",
    )

    with pytest.raises(
        jwt.InvalidTokenError,
        match="kid",
    ):
        decode_oidc_token(
            token
        )


def test_jwks_network_failure_is_propagated(
    oidc_environment,
    monkeypatch,
):
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    token = make_token(
        private_key
    )

    class FailingClient:
        def __init__(
            self,
            *args,
            **kwargs,
        ):
            pass

        def get_signing_key_from_jwt(
            self,
            token,
        ):
            raise (
                jwt.PyJWKClientConnectionError(
                    "identity provider unavailable"
                )
            )

    monkeypatch.setattr(
        jwt,
        "PyJWKClient",
        FailingClient,
    )

    clear_jwks_client_cache()

    with pytest.raises(
        jwt.PyJWKClientConnectionError
    ):
        decode_oidc_token(
            token
        )


def test_unknown_kid_error_is_propagated(
    oidc_environment,
    monkeypatch,
):
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    token = make_token(
        private_key,
        kid="rotated-kid",
    )

    class UnknownKeyClient:
        def __init__(
            self,
            *args,
            **kwargs,
        ):
            pass

        def get_signing_key_from_jwt(
            self,
            token,
        ):
            raise jwt.PyJWKClientError(
                "Unable to find a signing key"
            )

    monkeypatch.setattr(
        jwt,
        "PyJWKClient",
        UnknownKeyClient,
    )

    clear_jwks_client_cache()

    with pytest.raises(
        jwt.PyJWKClientError
    ):
        decode_oidc_token(
            token
        )


@pytest.mark.parametrize(
    "name,value",
    [
        (
            "RKJO_OIDC_JWKS_TIMEOUT_SECONDS",
            "0",
        ),
        (
            "RKJO_OIDC_JWKS_CACHE_LIFESPAN_SECONDS",
            "-1",
        ),
        (
            "RKJO_OIDC_JWKS_MAX_CACHED_KEYS",
            "0",
        ),
    ],
)
def test_invalid_hardening_values_are_rejected(
    oidc_environment,
    monkeypatch,
    name,
    value,
):
    monkeypatch.setenv(
        name,
        value,
    )

    with pytest.raises(
        RuntimeError,
        match="greater than 0",
    ):
        get_oidc_configuration()
