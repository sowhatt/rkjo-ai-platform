from datetime import (
    UTC,
    datetime,
)

from rkjo_api.dependencies import (
    get_rag_document_version_history_service,
)
from rkjo_api.main import app
from rkjo_kernel.rag.document_version_history import (
    DocumentVersionDetail,
)
from rkjo_kernel.rag.document_versioning import (
    DocumentVersion,
)


NOW = datetime.now(UTC)


class RecordingService:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def get_version(
        self,
        *,
        document_id,
        tenant_id,
        version_number,
    ):
        self.calls.append(
            (
                document_id,
                tenant_id,
                version_number,
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


def detail():
    return DocumentVersionDetail(
        document_id="doc-1",
        tenant_id="tenant-a",
        version=DocumentVersion(
            version_id="version-2",
            document_id="doc-1",
            tenant_id="tenant-a",
            version_number=2,
            content_hash="b" * 64,
            created_at=NOW,
        ),
        is_current=True,
    )


def test_viewer_reads_exact_own_version(
    client,
    viewer_headers,
):
    service = RecordingService(
        detail()
    )
    install(service)

    try:
        response = client.get(
            "/rag/documents/doc-1/versions/2",
            headers=viewer_headers,
        )
    finally:
        clear()

    assert response.status_code == 200

    payload = response.json()

    assert payload["document_id"] == "doc-1"
    assert payload["version_number"] == 2
    assert payload["version_id"] == "version-2"
    assert payload["is_current"] is True

    assert service.calls == [
        (
            "doc-1",
            "tenant-a",
            2,
        )
    ]


def test_missing_or_cross_tenant_version_is_404(
    client,
    viewer_headers,
):
    service = RecordingService(None)
    install(service)

    try:
        response = client.get(
            "/rag/documents/doc-1/versions/99",
            headers=viewer_headers,
        )
    finally:
        clear()

    assert response.status_code == 404

    assert response.json() == {
        "detail": (
            "Document version not found."
        )
    }


def test_zero_version_is_422(
    client,
    viewer_headers,
):
    class InvalidVersionService:
        def get_version(
            self,
            *,
            document_id,
            tenant_id,
            version_number,
        ):
            raise ValueError(
                "version_number must be greater "
                "than or equal to 1."
            )

    install(InvalidVersionService())

    try:
        response = client.get(
            "/rag/documents/doc-1/versions/0",
            headers=viewer_headers,
        )
    finally:
        clear()

    assert response.status_code == 422


def test_exact_version_requires_authentication(
    client,
):
    response = client.get(
        "/rag/documents/doc-1/versions/2"
    )

    assert response.status_code == 401
