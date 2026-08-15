"""Resolve Bearer credentials from local JWT or OIDC."""

from __future__ import annotations

import os

import jwt

from rkjo_api.jwt_auth import resolve_jwt_role
from rkjo_api.oidc_auth import resolve_oidc_identity
from rkjo_api.security import ApiRole


def oidc_is_configured() -> bool:
    """Return whether an OIDC provider is configured."""

    required = (
        "RKJO_OIDC_ISSUER",
        "RKJO_OIDC_AUDIENCE",
        "RKJO_OIDC_JWKS_URL",
    )

    return all(
        os.getenv(name, "").strip()
        for name in required
    )


def resolve_bearer_identity(
    token: str,
) -> tuple[str, ApiRole]:
    """Validate Bearer token against trusted auth mechanisms."""

    local_error: Exception | None = None

    try:
        return resolve_jwt_role(
            token
        )

    except (
        jwt.PyJWTError,
        ValueError,
        RuntimeError,
    ) as exc:
        local_error = exc

    if oidc_is_configured():
        return resolve_oidc_identity(
            token
        )

    if local_error is not None:
        raise local_error

    raise ValueError(
        "Bearer token could not be authenticated."
    )
