"""Hardened OIDC/JWKS token validation for RKJO API."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt

from rkjo_api.security import ApiRole
from rkjo_kernel.logging.logger import get_logger
from rkjo_kernel.logging.structured import structured_log


logger = get_logger(
    "rkjo.api.oidc"
)


@dataclass(frozen=True, slots=True)
class OIDCConfiguration:
    """Trusted OIDC provider configuration."""

    issuer: str
    audience: str
    jwks_url: str
    algorithm: str = "RS256"
    jwks_timeout_seconds: float = 5.0
    jwks_cache_lifespan_seconds: float = 300.0
    jwks_max_cached_keys: int = 16


def _read_required(
    name: str,
) -> str:
    value = os.getenv(name)

    if value is None or not value.strip():
        raise RuntimeError(
            f"{name} is not configured."
        )

    return value.strip()


def _read_float(
    name: str,
    default: float,
) -> float:
    value = os.getenv(name)

    if value is None:
        return default

    try:
        parsed = float(value)
    except ValueError as exc:
        raise RuntimeError(
            f"{name} must be a number."
        ) from exc

    if parsed <= 0:
        raise RuntimeError(
            f"{name} must be greater than 0."
        )

    return parsed


def _read_int(
    name: str,
    default: int,
) -> int:
    value = os.getenv(name)

    if value is None:
        return default

    try:
        parsed = int(value)
    except ValueError as exc:
        raise RuntimeError(
            f"{name} must be an integer."
        ) from exc

    if parsed <= 0:
        raise RuntimeError(
            f"{name} must be greater than 0."
        )

    return parsed


def get_oidc_configuration() -> OIDCConfiguration:
    """Load trusted OIDC settings from environment."""

    algorithm = os.getenv(
        "RKJO_OIDC_ALGORITHM",
        "RS256",
    ).strip()

    if not algorithm:
        raise RuntimeError(
            "RKJO_OIDC_ALGORITHM must not be empty."
        )

    return OIDCConfiguration(
        issuer=_read_required(
            "RKJO_OIDC_ISSUER"
        ),
        audience=_read_required(
            "RKJO_OIDC_AUDIENCE"
        ),
        jwks_url=_read_required(
            "RKJO_OIDC_JWKS_URL"
        ),
        algorithm=algorithm,
        jwks_timeout_seconds=_read_float(
            "RKJO_OIDC_JWKS_TIMEOUT_SECONDS",
            5.0,
        ),
        jwks_cache_lifespan_seconds=_read_float(
            "RKJO_OIDC_JWKS_CACHE_LIFESPAN_SECONDS",
            300.0,
        ),
        jwks_max_cached_keys=_read_int(
            "RKJO_OIDC_JWKS_MAX_CACHED_KEYS",
            16,
        ),
    )


@lru_cache(maxsize=8)
def _build_jwks_client(
    jwks_url: str,
    timeout: float,
    lifespan: float,
    max_cached_keys: int,
) -> jwt.PyJWKClient:
    """Build and cache a hardened JWKS client."""

    return jwt.PyJWKClient(
        jwks_url,
        cache_keys=True,
        max_cached_keys=max_cached_keys,
        cache_jwk_set=True,
        lifespan=lifespan,
        timeout=timeout,
        headers={
            "User-Agent": (
                "rkjo-ai-platform/oidc"
            ),
        },
    )


def clear_jwks_client_cache() -> None:
    """Clear cached JWKS clients, mainly for tests/config reload."""

    _build_jwks_client.cache_clear()


def get_jwks_client(
    config: OIDCConfiguration,
) -> jwt.PyJWKClient:
    """Return a cached PyJWKClient for one trusted provider."""

    return _build_jwks_client(
        config.jwks_url,
        config.jwks_timeout_seconds,
        config.jwks_cache_lifespan_seconds,
        config.jwks_max_cached_keys,
    )


def _require_kid(
    token: str,
) -> str:
    """Require a non-empty JWT kid header."""

    header = jwt.get_unverified_header(
        token
    )

    kid = header.get(
        "kid"
    )

    if not isinstance(kid, str) or not kid.strip():
        raise jwt.InvalidTokenError(
            "OIDC token is missing a valid kid header."
        )

    return kid.strip()


def decode_oidc_token(
    token: str,
) -> dict[str, Any]:
    """Verify one OIDC JWT using cached provider JWKS."""

    if not token or not token.strip():
        raise ValueError(
            "OIDC token must not be empty."
        )

    config = get_oidc_configuration()

    kid = _require_kid(
        token
    )

    client = get_jwks_client(
        config
    )

    try:
        signing_key = (
            client.get_signing_key_from_jwt(
                token
            )
        )

        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=[
                config.algorithm
            ],
            issuer=config.issuer,
            audience=config.audience,
            options={
                "require": [
                    "sub",
                    "role",
                    "iss",
                    "aud",
                    "iat",
                    "exp",
                ]
            },
        )

    except jwt.PyJWKClientConnectionError as exc:
        structured_log(
            logger,
            level=logging.ERROR,
            event="auth.oidc.jwks_unavailable",
            issuer=config.issuer,
            audience=config.audience,
            kid=kid,
            error=str(exc),
        )
        raise

    except jwt.PyJWKClientError as exc:
        structured_log(
            logger,
            level=logging.WARNING,
            event="auth.oidc.signing_key_error",
            issuer=config.issuer,
            audience=config.audience,
            kid=kid,
            error=str(exc),
        )
        raise

    except jwt.PyJWTError as exc:
        structured_log(
            logger,
            level=logging.WARNING,
            event="auth.oidc.token_rejected",
            issuer=config.issuer,
            audience=config.audience,
            kid=kid,
            error=str(exc),
        )
        raise

    structured_log(
        logger,
        event="auth.oidc.token_validated",
        issuer=config.issuer,
        audience=config.audience,
        kid=kid,
        subject=payload.get("sub"),
        role=payload.get("role"),
    )

    return payload


def resolve_oidc_identity(
    token: str,
) -> tuple[str, ApiRole]:
    """Resolve validated OIDC identity and RKJO role."""

    payload = decode_oidc_token(
        token
    )

    subject = str(
        payload["sub"]
    ).strip()

    if not subject:
        raise ValueError(
            "OIDC subject must not be empty."
        )

    try:
        role = ApiRole(
            payload["role"]
        )

    except ValueError as exc:
        raise ValueError(
            "OIDC token contains an invalid role."
        ) from exc

    return subject, role
