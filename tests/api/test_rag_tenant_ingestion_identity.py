import pytest
from fastapi import HTTPException

from rkjo_api.identity import (
    AuthenticatedIdentity,
    bind_identity_metadata_tenant,
)
from rkjo_api.security import ApiRole


def identity(
    tenant_id,
):
    return AuthenticatedIdentity(
        subject="operator-1",
        role=ApiRole.OPERATOR,
        tenant_id=tenant_id,
    )


def test_ingestion_tenant_is_injected():
    result = bind_identity_metadata_tenant(
        identity=identity(
            "tenant-a"
        ),
        metadata={
            "country": "benin",
            "domain": "agriculture",
        },
    )

    assert result == {
        "country": "benin",
        "domain": "agriculture",
        "tenant_id": "tenant-a",
    }


def test_matching_ingestion_tenant_is_allowed():
    result = bind_identity_metadata_tenant(
        identity=identity(
            "tenant-a"
        ),
        metadata={
            "tenant_id": "tenant-a",
            "domain": "agriculture",
        },
    )

    assert (
        result["tenant_id"]
        == "tenant-a"
    )


def test_cross_tenant_ingestion_is_forbidden():
    with pytest.raises(
        HTTPException,
    ) as exc:
        bind_identity_metadata_tenant(
            identity=identity(
                "tenant-a"
            ),
            metadata={
                "tenant_id": "tenant-b"
            },
        )

    assert exc.value.status_code == 403

    assert exc.value.detail == (
        "Cross-tenant ingestion "
        "is not permitted."
    )


def test_unbound_identity_preserves_metadata():
    metadata = {
        "tenant_id": "tenant-b",
        "domain": "agriculture",
    }

    result = bind_identity_metadata_tenant(
        identity=identity(None),
        metadata=metadata,
    )

    assert result == metadata
    assert result is not metadata


def test_invalid_ingestion_tenant_is_rejected():
    with pytest.raises(
        HTTPException,
    ) as exc:
        bind_identity_metadata_tenant(
            identity=identity(
                "tenant-a"
            ),
            metadata={
                "tenant_id": {
                    "bad": "value"
                }
            },
        )

    assert exc.value.status_code == 422
