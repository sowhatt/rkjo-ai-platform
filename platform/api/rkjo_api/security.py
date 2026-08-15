"""Authentication and RBAC primitives for RKJO API."""

from __future__ import annotations

import os
import secrets
from enum import StrEnum


API_KEY_HEADER = "X-API-Key"


class ApiRole(StrEnum):
    """API authorization roles ordered by privilege."""

    VIEWER = "viewer"
    OPERATOR = "operator"
    ADMIN = "admin"


ROLE_PRIORITY = {
    ApiRole.VIEWER: 1,
    ApiRole.OPERATOR: 2,
    ApiRole.ADMIN: 3,
}


PROTECTED_PATH_PREFIXES = (
    "/workflows",
    "/metrics",
    "/rag",
)


def _read_secret(
    name: str,
) -> str | None:
    value = os.getenv(name)

    if value is None:
        return None

    value = value.strip()

    return value or None


def get_configured_api_key() -> str | None:
    """Return the legacy admin API key."""

    return _read_secret(
        "RKJO_API_KEY"
    )


def get_configured_role_keys(
) -> dict[ApiRole, str]:
    """Return configured RBAC API keys."""

    result: dict[ApiRole, str] = {}

    viewer = _read_secret(
        "RKJO_VIEWER_API_KEY"
    )

    operator = _read_secret(
        "RKJO_OPERATOR_API_KEY"
    )

    admin = _read_secret(
        "RKJO_ADMIN_API_KEY"
    )

    if viewer:
        result[ApiRole.VIEWER] = viewer

    if operator:
        result[ApiRole.OPERATOR] = operator

    if admin:
        result[ApiRole.ADMIN] = admin

    return result


def is_protected_path(
    path: str,
) -> bool:
    """Return whether authentication is required."""

    return any(
        path == prefix
        or path.startswith(
            prefix + "/"
        )
        for prefix in PROTECTED_PATH_PREFIXES
    )


def resolve_api_role(
    provided_api_key: str | None,
) -> ApiRole | None:
    """Resolve an authenticated API key to its role."""

    configured = (
        get_configured_role_keys()
    )

    legacy_api_key = (
        get_configured_api_key()
    )

    if (
        not configured
        and legacy_api_key is None
    ):
        raise RuntimeError(
            "No RKJO API authentication key "
            "is configured."
        )

    if provided_api_key is None:
        return None

    # Backward compatibility:
    # RKJO_API_KEY always maps to ADMIN,
    # even when RKJO_ADMIN_API_KEY also exists.
    if (
        legacy_api_key is not None
        and secrets.compare_digest(
            provided_api_key,
            legacy_api_key,
        )
    ):
        return ApiRole.ADMIN

    # Check role-specific credentials.
    for role, configured_key in (
        configured.items()
    ):
        if secrets.compare_digest(
            provided_api_key,
            configured_key,
        ):
            return role

    return None


def verify_api_key(
    provided_api_key: str | None,
) -> bool:
    """Backward-compatible authentication check."""

    return (
        resolve_api_role(
            provided_api_key
        )
        is not None
    )


def required_role_for_request(
    *,
    method: str,
    path: str,
) -> ApiRole:
    """Return the minimum role required by an API operation."""

    normalized_method = method.upper()

    # Operational metrics are readable
    # by the lowest authenticated role.
    if path == "/metrics":
        return ApiRole.VIEWER

    # Semantic retrieval is read-only even though
    # HTTP POST is used to carry the search payload.
    if (
        path == "/rag/search"
        and normalized_method == "POST"
    ):
        return ApiRole.VIEWER

    # Grounded RAG answering is also read-only.
    if (
        path == "/rag/answer"
        and normalized_method == "POST"
    ):
        return ApiRole.VIEWER

    if path.startswith(
        "/rag"
    ):
        if normalized_method == "GET":
            return ApiRole.VIEWER

        if normalized_method in {
            "POST",
            "PUT",
            "PATCH",
        }:
            return ApiRole.OPERATOR

        if normalized_method == "DELETE":
            return ApiRole.ADMIN

    if path.startswith(
        "/workflows"
    ):
        if normalized_method == "GET":
            return ApiRole.VIEWER

        if normalized_method in {
            "POST",
            "PUT",
            "PATCH",
        }:
            return ApiRole.OPERATOR

        if normalized_method == "DELETE":
            return ApiRole.ADMIN

    # Protected resources default to
    # the safest privilege.
    return ApiRole.ADMIN


def role_allows(
    *,
    actual_role: ApiRole,
    required_role: ApiRole,
) -> bool:
    """Return whether a role satisfies a required privilege."""

    return (
        ROLE_PRIORITY[actual_role]
        >= ROLE_PRIORITY[required_role]
    )
