from rkjo_api.dependencies import (
    get_rag_document_replacement_service,
)
from rkjo_api.main import app
from rkjo_kernel.rag.document_replacement import (
    DocumentReplacementResult,
)


class RecordingReplacementService:
    def __init__(
        self,
        result,
    ):
        self.result = result
        self.calls = []

    def replace_document(
        self,
        document_id,
        path,
        *,
        metadata=None,
        filters=None,
    ):
        self.calls.append(
            {
                "document_id": document_id,
                "metadata": metadata,
                "filters": filters,
            }
        )

        return self.result


def install(service):
    app.dependency_overrides[
        get_rag_document_replacement_service
    ] = lambda: service


def clear():
    app.dependency_overrides.pop(
        get_rag_document_replacement_service,
        None,
    )


def test_operator_replaces_document_in_own_tenant(
    client,
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        "tenant-a",
    )

    service = RecordingReplacementService(
        DocumentReplacementResult(
            document_id="doc-1",
            old_deleted_chunk_count=1,
            old_deleted_hash_count=1,
            content_hash="b" * 64,
            chunk_count=2,
        )
    )

    install(service)

    try:
        response = client.put(
            "/rag/documents/doc-1",
            headers={
                "X-API-Key": "rkjo-operator-key"
            },
            files={
                "file": (
                    "updated.txt",
                    b"updated content",
                    "text/plain",
                )
            },
            data={
                "metadata": (
                    '{"domain":"agriculture"}'
                )
            },
        )
    finally:
        clear()

    assert response.status_code == 200

    call = service.calls[0]

    assert (
        call["metadata"]["tenant_id"]
        == "tenant-a"
    )

    assert (
        call["filters"].metadata
        == {"tenant_id": "tenant-a"}
    )


def test_cross_tenant_replace_is_hidden_as_404(
    client,
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        "tenant-a",
    )

    service = RecordingReplacementService(
        None
    )

    install(service)

    try:
        response = client.put(
            "/rag/documents/secret-doc",
            headers={
                "X-API-Key": "rkjo-operator-key"
            },
            files={
                "file": (
                    "updated.txt",
                    b"updated content",
                    "text/plain",
                )
            },
            data={
                "metadata": (
                    '{"domain":"agriculture"}'
                )
            },
        )
    finally:
        clear()

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Document not found."
    }


def test_cross_tenant_metadata_is_blocked_before_replace(
    client,
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        "tenant-a",
    )

    service = RecordingReplacementService(
        None
    )

    install(service)

    try:
        response = client.put(
            "/rag/documents/doc-1",
            headers={
                "X-API-Key": "rkjo-operator-key"
            },
            files={
                "file": (
                    "updated.txt",
                    b"updated content",
                    "text/plain",
                )
            },
            data={
                "metadata": (
                    '{"tenant_id":"tenant-b"}'
                )
            },
        )
    finally:
        clear()

    assert response.status_code == 403
    assert service.calls == []


def test_viewer_cannot_replace_document(
    client,
):
    response = client.put(
        "/rag/documents/doc-1",
        headers={
            "X-API-Key": "rkjo-viewer-key"
        },
        files={
            "file": (
                "updated.txt",
                b"updated content",
                "text/plain",
            )
        },
    )

    assert response.status_code == 403
