from pathlib import Path

from rkjo_api.dependencies import (
    get_rag_ingestion_pipeline,
)
from rkjo_api.main import app
from rkjo_kernel.rag.ingestion_models import (
    IngestionResult,
)


class RecordingPipeline:
    def __init__(self):
        self.calls = []

    def ingest_file(
        self,
        path,
        *,
        document_id=None,
        metadata=None,
    ):
        source = Path(path)

        self.calls.append(
            {
                "document_id": document_id,
                "metadata": metadata,
                "content": source.read_text(
                    encoding="utf-8"
                ),
            }
        )

        return IngestionResult(
            document_id=(
                document_id
                or "generated"
            ),
            content_hash="a" * 64,
            chunk_count=1,
            duplicate=False,
        )


def install_pipeline(
    pipeline,
):
    app.dependency_overrides[
        get_rag_ingestion_pipeline
    ] = lambda: pipeline


def clear_pipeline():
    app.dependency_overrides.pop(
        get_rag_ingestion_pipeline,
        None,
    )


def operator_headers():
    return {
        "X-API-Key": "rkjo-operator-key"
    }


def test_api_injects_operator_tenant(
    client,
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        "tenant-a",
    )

    pipeline = RecordingPipeline()
    install_pipeline(pipeline)

    try:
        response = client.post(
            "/rag/documents",
            headers=operator_headers(),
            files={
                "file": (
                    "tenant.txt",
                    b"tenant knowledge",
                    "text/plain",
                )
            },
            data={
                "document_id": "tenant-doc-1",
                "metadata": (
                    '{"domain":"agriculture"}'
                ),
            },
        )
    finally:
        clear_pipeline()

    assert response.status_code == 201
    assert len(pipeline.calls) == 1

    assert (
        pipeline.calls[0][
            "metadata"
        ]["tenant_id"]
        == "tenant-a"
    )


def test_api_accepts_matching_operator_tenant(
    client,
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        "tenant-a",
    )

    pipeline = RecordingPipeline()
    install_pipeline(pipeline)

    try:
        response = client.post(
            "/rag/documents",
            headers=operator_headers(),
            files={
                "file": (
                    "tenant.txt",
                    b"tenant knowledge",
                    "text/plain",
                )
            },
            data={
                "metadata": (
                    '{"tenant_id":"tenant-a",'
                    '"domain":"agriculture"}'
                ),
            },
        )
    finally:
        clear_pipeline()

    assert response.status_code == 201
    assert len(pipeline.calls) == 1


def test_api_blocks_cross_tenant_ingestion(
    client,
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        "tenant-a",
    )

    pipeline = RecordingPipeline()
    install_pipeline(pipeline)

    try:
        response = client.post(
            "/rag/documents",
            headers=operator_headers(),
            files={
                "file": (
                    "tenant.txt",
                    b"tenant knowledge",
                    "text/plain",
                )
            },
            data={
                "metadata": (
                    '{"tenant_id":"tenant-b",'
                    '"domain":"sante"}'
                ),
            },
        )
    finally:
        clear_pipeline()

    assert response.status_code == 403

    assert response.json() == {
        "detail": (
            "Cross-tenant ingestion "
            "is not permitted."
        )
    }

    # Critical: rejected before pipeline ingestion.
    assert pipeline.calls == []


def test_api_unbound_operator_remains_compatible(
    client,
    monkeypatch,
):
    monkeypatch.delenv(
        "RKJO_OPERATOR_TENANT_ID",
        raising=False,
    )

    pipeline = RecordingPipeline()
    install_pipeline(pipeline)

    try:
        response = client.post(
            "/rag/documents",
            headers=operator_headers(),
            files={
                "file": (
                    "tenant.txt",
                    b"tenant knowledge",
                    "text/plain",
                )
            },
            data={
                "metadata": (
                    '{"tenant_id":"legacy-tenant"}'
                ),
            },
        )
    finally:
        clear_pipeline()

    assert response.status_code == 201

    assert (
        pipeline.calls[0][
            "metadata"
        ]["tenant_id"]
        == "legacy-tenant"
    )
