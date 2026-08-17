from pathlib import Path

import pytest

from rkjo_kernel.rag.document_replacement import (
    DocumentReplacementService,
)
from rkjo_kernel.rag.ingestion_models import (
    PreparedChunk,
    PreparedIngestion,
)
from rkjo_kernel.rag.models import (
    DocumentChunk,
)
from rkjo_kernel.rag.retrieval_filters import (
    RetrievalFilters,
)


def prepared():
    return PreparedIngestion(
        document_id="doc-1",
        content_hash="b" * 64,
        chunks=(
            PreparedChunk(
                chunk=DocumentChunk(
                    document_id="doc-1",
                    chunk_id="chunk-new",
                    content="new content",
                    chunk_index=0,
                    metadata={
                        "tenant_id": "tenant-a",
                        "content_hash": "b" * 64,
                    },
                ),
                embedding=(
                    1.0,
                    0.0,
                    0.0,
                ),
            ),
        ),
    )


class FakePipeline:
    def __init__(
        self,
        *,
        fail=False,
    ):
        self.fail = fail
        self.calls = []

    def prepare_file(
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

        if self.fail:
            raise RuntimeError(
                "embedding failure"
            )

        return prepared()


class FakeRepository:
    def __init__(
        self,
        result=(1, 1),
    ):
        self.result = result
        self.calls = []

    def replace(
        self,
        prepared,
        *,
        filters=None,
    ):
        self.calls.append(
            (
                prepared,
                filters,
            )
        )
        return self.result


def test_replace_prepares_then_atomically_swaps(
    tmp_path,
):
    pipeline = FakePipeline()
    repository = FakeRepository()

    service = DocumentReplacementService(
        ingestion_pipeline=pipeline,
        replacement_repository=repository,
    )

    source = tmp_path / "new.txt"
    source.write_text(
        "new",
        encoding="utf-8",
    )

    filters = RetrievalFilters(
        metadata={
            "tenant_id": "tenant-a"
        }
    )

    result = service.replace_document(
        "doc-1",
        source,
        filters=filters,
    )

    assert result.document_id == "doc-1"
    assert result.old_deleted_chunk_count == 1
    assert result.old_deleted_hash_count == 1
    assert result.chunk_count == 1
    assert len(repository.calls) == 1


def test_preparation_failure_never_calls_repository(
    tmp_path,
):
    pipeline = FakePipeline(
        fail=True
    )
    repository = FakeRepository()

    service = DocumentReplacementService(
        ingestion_pipeline=pipeline,
        replacement_repository=repository,
    )

    source = tmp_path / "new.txt"
    source.write_text(
        "new",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="embedding failure",
    ):
        service.replace_document(
            "doc-1",
            source,
        )

    assert repository.calls == []


def test_missing_scoped_document_returns_none(
    tmp_path,
):
    pipeline = FakePipeline()
    repository = FakeRepository(
        result=None
    )

    service = DocumentReplacementService(
        ingestion_pipeline=pipeline,
        replacement_repository=repository,
    )

    source = tmp_path / "new.txt"
    source.write_text(
        "new",
        encoding="utf-8",
    )

    assert (
        service.replace_document(
            "doc-1",
            source,
        )
        is None
    )
