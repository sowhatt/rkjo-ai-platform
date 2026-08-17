from pathlib import Path

import pytest

from rkjo_kernel.rag.document_lifecycle import (
    DocumentDeletionResult,
)
from rkjo_kernel.rag.document_replacement import (
    DocumentReplacementService,
)
from rkjo_kernel.rag.ingestion_models import (
    IngestionResult,
)
from rkjo_kernel.rag.retrieval_filters import (
    RetrievalFilters,
)


class FakeLifecycleService:
    def __init__(
        self,
        result,
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
        self.calls.append(
            (
                Path(path),
                document_id,
                metadata,
            )
        )

        return IngestionResult(
            document_id=document_id,
            content_hash="b" * 64,
            chunk_count=2,
            duplicate=self.duplicate,
        )


def deletion():
    return DocumentDeletionResult(
        document_id="doc-1",
        deleted_chunk_count=3,
        deleted_hash_count=1,
    )


def test_replace_deletes_then_reingests(
    tmp_path,
):
    lifecycle = FakeLifecycleService(
        deletion()
    )
    pipeline = FakePipeline()

    service = DocumentReplacementService(
        lifecycle_service=lifecycle,
        ingestion_pipeline=pipeline,
    )

    path = tmp_path / "new.txt"
    path.write_text(
        "new content",
        encoding="utf-8",
    )

    filters = RetrievalFilters(
        metadata={
            "tenant_id": "tenant-a"
        }
    )

    result = service.replace_document(
        "doc-1",
        path,
        metadata={
            "tenant_id": "tenant-a"
        },
        filters=filters,
    )

    assert result.document_id == "doc-1"
    assert result.old_deleted_chunk_count == 3
    assert result.old_deleted_hash_count == 1
    assert result.chunk_count == 2

    assert lifecycle.calls == [
        (
            "doc-1",
            filters,
        )
    ]

    assert pipeline.calls[0][1] == "doc-1"


def test_replace_missing_scoped_document_returns_none(
    tmp_path,
):
    lifecycle = FakeLifecycleService(
        None
    )
    pipeline = FakePipeline()

    service = DocumentReplacementService(
        lifecycle_service=lifecycle,
        ingestion_pipeline=pipeline,
    )

    path = tmp_path / "new.txt"
    path.write_text(
        "new content",
        encoding="utf-8",
    )

    result = service.replace_document(
        "doc-1",
        path,
    )

    assert result is None
    assert pipeline.calls == []


def test_duplicate_replacement_is_rejected(
    tmp_path,
):
    lifecycle = FakeLifecycleService(
        deletion()
    )

    pipeline = FakePipeline(
        duplicate=True
    )

    service = DocumentReplacementService(
        lifecycle_service=lifecycle,
        ingestion_pipeline=pipeline,
    )

    path = tmp_path / "new.txt"
    path.write_text(
        "duplicate",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        service.replace_document(
            "doc-1",
            path,
        )
