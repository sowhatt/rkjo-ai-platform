import pytest
from fastapi import HTTPException

from rkjo_api.identity import (
    AuthenticatedIdentity,
    bind_identity_tenant,
)
from rkjo_api.security import ApiRole
from rkjo_kernel.rag.retrieval_filters import (
    RetrievalFilters,
)


def identity(tenant_id):
    return AuthenticatedIdentity(
        subject="user-1",
        role=ApiRole.VIEWER,
        tenant_id=tenant_id,
    )


def test_tenant_is_injected_when_missing():
    result = bind_identity_tenant(
        identity=identity("tenant-a"),
        filters=RetrievalFilters(
            metadata={
                "domain": "agriculture"
            }
        ),
    )

    assert result.metadata == {
        "domain": "agriculture",
        "tenant_id": "tenant-a",
    }


def test_matching_tenant_is_allowed():
    result = bind_identity_tenant(
        identity=identity("tenant-a"),
        filters=RetrievalFilters(
            metadata={
                "tenant_id": "tenant-a"
            }
        ),
    )

    assert (
        result.metadata["tenant_id"]
        == "tenant-a"
    )


def test_cross_tenant_is_forbidden():
    with pytest.raises(
        HTTPException,
    ) as exc:
        bind_identity_tenant(
            identity=identity("tenant-a"),
            filters=RetrievalFilters(
                metadata={
                    "tenant_id": "tenant-b"
                }
            ),
        )

    assert exc.value.status_code == 403


def test_unbound_identity_preserves_filters():
    filters = RetrievalFilters(
        metadata={
            "tenant_id": "tenant-b"
        }
    )

    result = bind_identity_tenant(
        identity=identity(None),
        filters=filters,
    )

    assert result is filters


def test_bound_identity_without_filters_creates_filter():
    result = bind_identity_tenant(
        identity=identity("tenant-a"),
        filters=None,
    )

    assert result.metadata == {
        "tenant_id": "tenant-a"
    }
