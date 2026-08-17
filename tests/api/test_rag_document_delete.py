from rkjo_api.dependencies import (
    get_rag_document_lifecycle_service,
)
from rkjo_api.main import app
from rkjo_kernel.rag.document_lifecycle import (
    DocumentDeletionResult,
)


class RecordingLifecycleService:
    def __init__(
        self,
        *,
        result=None,
    ):
        self.result = result
        self.calls = []

    def delete_document(
        self,
        document_id,
        *,
        filters=None,
    ):
        self.calls.append(
            (
                document_id,
                filters,
            )
        )

        return self.result


def install(service):
    app.dependency_overrides[
        get_rag_document_lifecycle_service
    ] = lambda: service


def clear():
    app.dependency_overrides.pop(
        get_rag_document_lifecycle_service,
        None,
    )


def test_admin_deletes_document_inside_tenant(
    client,
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_ADMIN_TENANT_ID",
        "tenant-a",
    )

    service = RecordingLifecycleService(
        result=DocumentDeletionResult(
            document_id="doc-1",
            deleted_chunk_count=2,
            deleted_hash_count=1,
        )
    )

    install(service)

    try:
        response = client.delete(
            "/rag/documents/doc-1",
            headers={
                "X-API-Key": "rkjo-admin-key"
            },
        )
    finally:
        clear()

    assert response.status_code == 200

    assert response.json() == {
        "document_id": "doc-1",
        "deleted_chunk_count": 2,
        "deleted_hash_count": 1,
    }

    _, filters = service.calls[0]

    assert filters.metadata == {
        "tenant_id": "tenant-a"
    }


def test_operator_cannot_delete_document(
    client,
):
    response = client.delete(
        "/rag/documents/doc-1",
        headers={
            "X-API-Key": "rkjo-operator-key"
        },
    )

    assert response.status_code == 403


def test_missing_or_cross_tenant_document_returns_404(
    client,
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_ADMIN_TENANT_ID",
        "tenant-a",
    )

    service = RecordingLifecycleService(
        result=None
    )

    install(service)

    try:
        response = client.delete(
            "/rag/documents/secret-doc",
            headers={
                "X-API-Key": "rkjo-admin-key"
            },
        )
    finally:
        clear()

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Document not found."
    }


def test_delete_requires_authentication(
    client,
):
    response = client.delete(
        "/rag/documents/doc-1"
    )

    assert response.status_code == 401
