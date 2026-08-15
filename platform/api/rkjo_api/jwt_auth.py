"""JWT authentication helpers for RKJO API."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from rkjo_api.security import ApiRole


JWT_ALGORITHM = "HS256"


def get_jwt_secret() -> str | None:
    value = os.getenv(
        "RKJO_JWT_SECRET"
    )

    if value is None:
        return None

    value = value.strip()

    return value or None


def create_access_token(
    *,
    subject: str,
    role: ApiRole,
    expires_in_seconds: int = 3600,
) -> str:
    """Create a signed RKJO access token."""

    if not subject or not subject.strip():
        raise ValueError(
            "JWT subject must not be empty."
        )

    if expires_in_seconds <= 0:
        raise ValueError(
            "expires_in_seconds must be greater than 0."
        )

    secret = get_jwt_secret()

    if secret is None:
        raise RuntimeError(
            "RKJO_JWT_SECRET is not configured."
        )

    now = datetime.now(
        timezone.utc
    )

    payload: dict[str, Any] = {
        "sub": subject,
        "role": role.value,
        "iat": now,
        "exp": now + timedelta(
            seconds=expires_in_seconds
        ),
    }

    return jwt.encode(
        payload,
        secret,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(
    token: str,
) -> dict[str, Any]:
    """Verify and decode one RKJO access token."""

    if not token or not token.strip():
        raise ValueError(
            "JWT token must not be empty."
        )

    secret = get_jwt_secret()

    if secret is None:
        raise RuntimeError(
            "RKJO_JWT_SECRET is not configured."
        )

    return jwt.decode(
        token,
        secret,
        algorithms=[
            JWT_ALGORITHM
        ],
        options={
            "require": [
                "sub",
                "role",
                "iat",
                "exp",
            ]
        },
    )


def resolve_jwt_role(
    token: str,
) -> tuple[str, ApiRole]:
    """Return authenticated subject and role."""

    payload = decode_access_token(
        token
    )

    subject = str(
        payload["sub"]
    )

    try:
        role = ApiRole(
            payload["role"]
        )
    except ValueError as exc:
        raise ValueError(
            "JWT contains an invalid role."
        ) from exc

    return subject, role
