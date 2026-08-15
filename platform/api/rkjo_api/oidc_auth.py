"""OIDC/JWKS token validation for RKJO API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import jwt

from rkjo_api.security import ApiRole


@dataclass(frozen=True, slots=True)
class OIDCConfiguration:
    """Trusted OIDC provider configuration."""

    issuer: str
    audience: str
    jwks_url: str
    algorithm: str = "RS256"


def _read_required(
    name: str,
) -> str:
    value = os.getenv(name)

    if value is None or not value.strip():
        raise RuntimeError(
            f"{name} is not configured."
        )

    return value.strip()


def get_oidc_configuration() -> OIDCConfiguration:
    """Load trusted OIDC settings from environment."""

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
        algorithm=os.getenv(
            "RKJO_OIDC_ALGORITHM",
            "RS256",
        ).strip(),
    )


def decode_oidc_token(
    token: str,
) -> dict[str, Any]:
    """Verify one OIDC JWT using the provider JWKS."""

    if not token or not token.strip():
        raise ValueError(
            "OIDC token must not be empty."
        )

    config = get_oidc_configuration()

    jwks_client = jwt.PyJWKClient(
        config.jwks_url
    )

    signing_key = (
        jwks_client
        .get_signing_key_from_jwt(
            token
        )
    )

    return jwt.decode(
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
