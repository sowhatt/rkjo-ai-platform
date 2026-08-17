"""RAG document lifecycle operations."""

from __future__ import annotations

from dataclasses import dataclass

from rkjo_kernel.rag.postgres_deduplication import (
    PostgresDocumentHashRegistry,
)
from rkjo_kernel.rag.postgres_vector_store import (
    PostgresPgVectorStore,
)
from rkjo_kernel.rag.retrieval_filters import (
    RetrievalFilters,
)


@dataclass(frozen=True, slots=True)
class DocumentDeletionResult:
    document_id: str
    deleted_chunk_count: int
    deleted_hash_count: int


class DocumentLifecycleService:
    """Tenant-scoped document lifecycle service."""

    def __init__(
        self,
        *,
        vector_store: PostgresPgVectorStore,
        hash_registry: PostgresDocumentHashRegistry,
    ) -> None:
        self.vector_store = vector_store
        self.hash_registry = hash_registry

    def delete_document(
        self,
        document_id: str,
        *,
        filters: RetrievalFilters | None = None,
    ) -> DocumentDeletionResult | None:
        normalized_document_id = (
            document_id.strip()
        )

        if not normalized_document_id:
            raise ValueError(
                "document_id must not be empty."
            )

        deleted_chunks = (
            self.vector_store.delete_document(
                normalized_document_id,
                filters=filters,
            )
        )

        # Important security property:
        # if nothing was visible in this scope,
        # behave exactly like a missing document.
        if deleted_chunks == 0:
            return None

        deleted_hashes = (
            self.hash_registry.delete_document(
                normalized_document_id
            )
        )

        return DocumentDeletionResult(
            document_id=normalized_document_id,
            deleted_chunk_count=deleted_chunks,
            deleted_hash_count=deleted_hashes,
        )
