"""Authenticated RKJO API identity and tenant binding."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request

from rkjo_api.security import ApiRole
from rkjo_kernel.rag.retrieval_filters import (
    RetrievalFilters,
)


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    subject: str | None
    role: ApiRole
    tenant_id: str | None = None


def get_authenticated_identity(
    request: Request,
) -> AuthenticatedIdentity:
    role_raw = getattr(
        request.state,
        "api_role",
        None,
    )

    if role_raw is None:
        raise HTTPException(
            status_code=401,
            detail="Authenticated identity is unavailable.",
        )

    try:
        role = ApiRole(role_raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail="Authenticated role is invalid.",
        ) from exc

    return AuthenticatedIdentity(
        subject=getattr(
            request.state,
            "api_subject",
            None,
        ),
        role=role,
        tenant_id=getattr(
            request.state,
            "api_tenant_id",
            None,
        ),
    )


def bind_identity_tenant(
    *,
    identity: AuthenticatedIdentity,
    filters: RetrievalFilters | None,
) -> RetrievalFilters | None:
    """Enforce the authenticated tenant on retrieval filters."""

    tenant_id = identity.tenant_id

    if tenant_id is None:
        return filters

    metadata = dict(
        filters.metadata
        if filters is not None
        else {}
    )

    requested_tenant = metadata.get(
        "tenant_id"
    )

    if (
        requested_tenant is not None
        and requested_tenant != tenant_id
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Cross-tenant access is not permitted."
            ),
        )

    metadata["tenant_id"] = tenant_id

    return RetrievalFilters(
        metadata=metadata
    )



def bind_identity_metadata_tenant(
    *,
    identity: AuthenticatedIdentity,
    metadata: dict,
) -> dict:
    """Enforce authenticated tenant on document metadata."""

    tenant_id = identity.tenant_id

    # Backward-compatible identities remain unbound.
    if tenant_id is None:
        return dict(metadata)

    result = dict(metadata)

    requested_tenant = result.get(
        "tenant_id"
    )

    if requested_tenant is not None:
        if not isinstance(
            requested_tenant,
            str,
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "metadata.tenant_id "
                    "must be a string."
                ),
            )

        requested_tenant = (
            requested_tenant.strip()
        )

        if not requested_tenant:
            raise HTTPException(
                status_code=422,
                detail=(
                    "metadata.tenant_id "
                    "must not be empty."
                ),
            )

        if requested_tenant != tenant_id:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Cross-tenant ingestion "
                    "is not permitted."
                ),
            )

    result["tenant_id"] = tenant_id

    return result
