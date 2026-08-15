from pathlib import Path

import pytest

from rkjo_api.dependencies import (
    get_rag_ingestion_pipeline,
)
from rkjo_api.main import app
from rkjo_api import rag as rag_api
from rkjo_kernel.rag.ingestion_models import (
    IngestionResult,
)


class FakePipeline:

    def __init__(
        self,
        *,
        duplicate=False,
    ):
        self.duplicate = duplicate
        self.calls = []

    def ingest_file(
        self,
        path,
        *,
        document_id=None,
        metadata=None,
    ):
        source = Path(
            path
        )

        assert source.exists()

        self.calls.append(
            {
                "content": (
                    source.read_text(
                        encoding="utf-8"
                    )
                ),
                "document_id": (
                    document_id
                ),
                "metadata": metadata,
            }
        )

        return IngestionResult(
            document_id=(
                document_id
                or "generated-doc"
            ),
            content_hash=(
                "a" * 64
            ),
            chunk_count=(
                0
                if self.duplicate
                else 3
            ),
            duplicate=(
                self.duplicate
            ),
        )


@pytest.fixture
def operator_headers():
    return {
        "X-API-Key": (
            "rkjo-operator-key"
        )
    }


def override_pipeline(
    pipeline,
):
    app.dependency_overrides[
        get_rag_ingestion_pipeline
    ] = lambda: pipeline

    return pipeline


def clear_override():
    app.dependency_overrides.pop(
        get_rag_ingestion_pipeline,
        None,
    )


def test_rag_upload_requires_authentication(
    client,
):
    response = client.post(
        "/rag/documents",
        files={
            "file": (
                "knowledge.txt",
                b"agriculture knowledge",
                "text/plain",
            )
        },
    )

    assert response.status_code == 401


def test_viewer_cannot_upload_document(
    client,
):
    response = client.post(
        "/rag/documents",
        headers={
            "X-API-Key": (
                "rkjo-viewer-key"
            )
        },
        files={
            "file": (
                "knowledge.txt",
                b"agriculture knowledge",
                "text/plain",
            )
        },
    )

    assert response.status_code == 403


def test_operator_can_upload_document(
    client,
    operator_headers,
):
    pipeline = override_pipeline(
        FakePipeline()
    )

    try:
        response = client.post(
            "/rag/documents",
            headers=operator_headers,
            files={
                "file": (
                    "knowledge.txt",
                    b"soil rainfall crop yield",
                    "text/plain",
                )
            },
            data={
                "document_id": "rag-api-001",
                "metadata": (
                    '{"country":"benin"}'
                ),
            },
        )

    finally:
        clear_override()

    assert response.status_code == 201

    assert response.json() == {
        "document_id": "rag-api-001",
        "content_hash": "a" * 64,
        "chunk_count": 3,
        "duplicate": False,
    }

    assert len(
        pipeline.calls
    ) == 1

    call = pipeline.calls[0]

    assert (
        call["content"]
        == "soil rainfall crop yield"
    )

    assert call["metadata"][
        "country"
    ] == "benin"

    assert call["metadata"][
        "original_filename"
    ] == "knowledge.txt"


def test_duplicate_upload_returns_200(
    client,
    operator_headers,
):
    override_pipeline(
        FakePipeline(
            duplicate=True
        )
    )

    try:
        response = client.post(
            "/rag/documents",
            headers=operator_headers,
            files={
                "file": (
                    "knowledge.txt",
                    b"same document",
                    "text/plain",
                )
            },
        )

    finally:
        clear_override()

    assert response.status_code == 200

    assert (
        response.json()[
            "duplicate"
        ]
        is True
    )

    assert (
        response.json()[
            "chunk_count"
        ]
        == 0
    )


def test_unsupported_file_type_returns_415(
    client,
    operator_headers,
):
    override_pipeline(
        FakePipeline()
    )

    try:
        response = client.post(
            "/rag/documents",
            headers=operator_headers,
            files={
                "file": (
                    "data.csv",
                    b"a,b,c",
                    "text/csv",
                )
            },
        )

    finally:
        clear_override()

    assert response.status_code == 415


def test_invalid_metadata_returns_422(
    client,
    operator_headers,
):
    override_pipeline(
        FakePipeline()
    )

    try:
        response = client.post(
            "/rag/documents",
            headers=operator_headers,
            files={
                "file": (
                    "knowledge.txt",
                    b"knowledge",
                    "text/plain",
                )
            },
            data={
                "metadata": "{invalid-json"
            },
        )

    finally:
        clear_override()

    assert response.status_code == 422


def test_empty_upload_returns_422(
    client,
    operator_headers,
):
    override_pipeline(
        FakePipeline()
    )

    try:
        response = client.post(
            "/rag/documents",
            headers=operator_headers,
            files={
                "file": (
                    "empty.txt",
                    b"",
                    "text/plain",
                )
            },
        )

    finally:
        clear_override()

    assert response.status_code == 422


def test_upload_size_limit_returns_413(
    client,
    operator_headers,
    monkeypatch,
):
    override_pipeline(
        FakePipeline()
    )

    monkeypatch.setattr(
        rag_api,
        "MAX_UPLOAD_BYTES",
        5,
    )

    try:
        response = client.post(
            "/rag/documents",
            headers=operator_headers,
            files={
                "file": (
                    "large.txt",
                    b"123456",
                    "text/plain",
                )
            },
        )

    finally:
        clear_override()

    assert response.status_code == 413
