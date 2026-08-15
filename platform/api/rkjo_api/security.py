"""API-key security primitives for RKJO API."""

from __future__ import annotations

import os
import secrets


API_KEY_HEADER = "X-API-Key"

PROTECTED_PATH_PREFIXES = (
    "/workflows",
    "/metrics",
)


def get_configured_api_key() -> str | None:
    """Return the configured API key without providing a default."""

    value = os.getenv("RKJO_API_KEY")

    if value is None:
        return None

    value = value.strip()

    return value or None


def is_protected_path(
    path: str,
) -> bool:
    """Return whether an API path requires authentication."""

    return any(
        path == prefix
        or path.startswith(
            prefix + "/"
        )
        for prefix in PROTECTED_PATH_PREFIXES
    )


def verify_api_key(
    provided_api_key: str | None,
) -> bool:
    """Validate a provided key using constant-time comparison."""

    configured_api_key = (
        get_configured_api_key()
    )

    if configured_api_key is None:
        raise RuntimeError(
            "RKJO_API_KEY is not configured."
        )

    if provided_api_key is None:
        return False

    return secrets.compare_digest(
        provided_api_key,
        configured_api_key,
    )
