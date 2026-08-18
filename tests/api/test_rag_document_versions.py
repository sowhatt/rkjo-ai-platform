from datetime import (
    UTC,
    datetime,
)

from rkjo_api.dependencies import (
    get_rag_document_version_history_service,
)
from rkjo_api.main import app
from rkjo_kernel.rag.document_version_history import (
    DocumentVersionHistory,
)
from rkjo_kernel.rag.document_versioning import (
    DocumentVersion,
)


NOW = datetime.now(UTC)


class RecordingHistoryService:
    def __init__(
        self,
        result,
    ):
        self.result = result
        self.calls = []

    def get_history(
        self,
        *,
        document_id,
        tenant_id,
    ):
        self.calls.append(
            (
                document_id,
                tenant_id,
            )
        )

        return self.result


def install(service):
    app.dependency_overrides[
        get_rag_document_version_history_service
    ] = lambda: service


def clear():
    app.dependency_overrides.pop(
        get_rag_document_version_history_service,
        None,
    )


def history():
    return DocumentVersionHistory(
        document_id="doc-1",
        tenant_id="tenant-a",
        current_version=2,
        versions=(
            DocumentVersion(
                version_id="version-1",
                document_id="doc-1",
                tenant_id="tenant-a",
                version_number=1,
                content_hash="a" * 64,
                created_at=NOW,
            ),
            DocumentVersion(
                version_id="version-2",
                document_id="doc-1",
                tenant_id="tenant-a",
                version_number=2,
                content_hash="b" * 64,
                created_at=NOW,
            ),
        ),
    )


def test_viewer_can_read_own_document_history(
    client,
    viewer_headers,
):
    service = RecordingHistoryService(
        history()
    )

    install(service)

    try:
        response = client.get(
            "/rag/documents/doc-1/versions",
            headers=viewer_headers,
        )
    finally:
        clear()

    assert response.status_code == 200

    payload = response.json()

    assert payload["document_id"] == "doc-1"
    assert payload["current_version"] == 2

    assert [
        item["version_number"]
        for item in payload["versions"]
    ] == [1, 2]

    assert service.calls == [
        (
            "doc-1",
            "tenant-a",
        )
    ]


def test_missing_or_cross_tenant_history_returns_404(
    client,
    viewer_headers,
):
    service = RecordingHistoryService(
        None
    )

    install(service)

    try:
        response = client.get(
            "/rag/documents/secret-doc/versions",
            headers=viewer_headers,
        )
    finally:
        clear()

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Document not found."
    }


def test_history_requires_authentication(
    client,
):
    response = client.get(
        "/rag/documents/doc-1/versions"
    )

    assert response.status_code == 401
