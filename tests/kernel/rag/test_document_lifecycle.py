from rkjo_kernel.rag.document_lifecycle import (
    DocumentLifecycleService,
)
from rkjo_kernel.rag.retrieval_filters import (
    RetrievalFilters,
)


class FakeVectorStore:
    def __init__(self, deleted):
        self.deleted = deleted
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
        return self.deleted


class FakeHashRegistry:
    def __init__(self, deleted=1):
        self.deleted = deleted
        self.calls = []

    def delete_document(
        self,
        document_id,
    ):
        self.calls.append(
            document_id
        )
        return self.deleted


def test_delete_removes_chunks_and_hash():
    vector = FakeVectorStore(3)
    hashes = FakeHashRegistry(1)

    service = DocumentLifecycleService(
        vector_store=vector,
        hash_registry=hashes,
    )

    filters = RetrievalFilters(
        metadata={
            "tenant_id": "tenant-a"
        }
    )

    result = service.delete_document(
        "doc-1",
        filters=filters,
    )

    assert result.document_id == "doc-1"
    assert result.deleted_chunk_count == 3
    assert result.deleted_hash_count == 1
    assert hashes.calls == ["doc-1"]


def test_missing_scoped_document_does_not_touch_hash_registry():
    vector = FakeVectorStore(0)
    hashes = FakeHashRegistry(1)

    service = DocumentLifecycleService(
        vector_store=vector,
        hash_registry=hashes,
    )

    result = service.delete_document(
        "doc-1",
        filters=RetrievalFilters(
            metadata={
                "tenant_id": "tenant-a"
            }
        ),
    )

    assert result is None
    assert hashes.calls == []
