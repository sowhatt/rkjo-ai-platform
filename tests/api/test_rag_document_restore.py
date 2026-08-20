from rkjo_api.dependencies import (
    get_rag_document_restore_repository,
)
from rkjo_api.main import app
from rkjo_kernel.rag.document_restore import (
    DocumentRestoreResult,
)


class RecordingRestoreRepository:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def restore(
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

        if self.error is not None:
            raise self.error

        return self.result


def install(repository):
    app.dependency_overrides[
        get_rag_document_restore_repository
    ] = lambda: repository


def clear():
    app.dependency_overrides.pop(
        get_rag_document_restore_repository,
        None,
    )


def test_operator_restores_own_historical_version(
    client,
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        "tenant-a",
    )

    repository = RecordingRestoreRepository(
        result=DocumentRestoreResult(
            document_id="doc-1",
            restored_from_version=1,
            new_version=4,
            content_hash="a" * 64,
            chunk_count=2,
        )
    )

    install(repository)

    try:
        response = client.post(
            "/rag/documents/doc-1/versions/1/restore",
            headers={
                "X-API-Key": "rkjo-operator-key"
            },
        )
    finally:
        clear()

    assert response.status_code == 200

    payload = response.json()

    assert payload["document_id"] == "doc-1"
    assert payload["restored_from_version"] == 1
    assert payload["new_version"] == 4
    assert payload["chunk_count"] == 2

    assert repository.calls == [
        (
            "doc-1",
            "tenant-a",
            1,
        )
    ]


def test_missing_or_cross_tenant_restore_is_404(
    client,
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        "tenant-a",
    )

    repository = RecordingRestoreRepository(
        error=LookupError(
            "Document version not found."
        )
    )

    install(repository)

    try:
        response = client.post(
            "/rag/documents/doc-1/versions/99/restore",
            headers={
                "X-API-Key": "rkjo-operator-key"
            },
        )
    finally:
        clear()

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Document version not found."
    }


def test_current_version_restore_is_422(
    client,
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        "tenant-a",
    )

    repository = RecordingRestoreRepository(
        error=ValueError(
            "Cannot restore the current version."
        )
    )

    install(repository)

    try:
        response = client.post(
            "/rag/documents/doc-1/versions/3/restore",
            headers={
                "X-API-Key": "rkjo-operator-key"
            },
        )
    finally:
        clear()

    assert response.status_code == 422


def test_viewer_cannot_restore(
    client,
    viewer_headers,
):
    response = client.post(
        "/rag/documents/doc-1/versions/1/restore",
        headers=viewer_headers,
    )

    assert response.status_code == 403


def test_restore_requires_authentication(
    client,
):
    response = client.post(
        "/rag/documents/doc-1/versions/1/restore"
    )

    assert response.status_code == 401
