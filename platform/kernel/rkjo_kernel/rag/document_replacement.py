"""RAG document replacement and reindexing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rkjo_kernel.rag.document_lifecycle import (
    DocumentLifecycleService,
)
from rkjo_kernel.rag.ingestion import (
    DocumentIngestionPipeline,
)
from rkjo_kernel.rag.retrieval_filters import (
    RetrievalFilters,
)


@dataclass(frozen=True, slots=True)
class DocumentReplacementResult:
    document_id: str
    old_deleted_chunk_count: int
    old_deleted_hash_count: int
    content_hash: str
    chunk_count: int


class DocumentReplacementService:
    """Replace and reindex a tenant-scoped RAG document."""

    def __init__(
        self,
        *,
        lifecycle_service: DocumentLifecycleService,
        ingestion_pipeline: DocumentIngestionPipeline,
    ) -> None:
        self.lifecycle_service = lifecycle_service
        self.ingestion_pipeline = ingestion_pipeline

    def replace_document(
        self,
        document_id: str,
        path: str | Path,
        *,
        metadata: dict | None = None,
        filters: RetrievalFilters | None = None,
    ) -> DocumentReplacementResult | None:
        normalized_document_id = (
            document_id.strip()
        )

        if not normalized_document_id:
            raise ValueError(
                "document_id must not be empty."
            )

        deletion = (
            self.lifecycle_service.delete_document(
                normalized_document_id,
                filters=filters,
            )
        )

        # Missing and cross-tenant documents are deliberately
        # indistinguishable.
        if deletion is None:
            return None

        ingestion = (
            self.ingestion_pipeline.ingest_file(
                path,
                document_id=normalized_document_id,
                metadata=metadata,
            )
        )

        if ingestion.duplicate:
            raise ValueError(
                "Replacement content duplicates "
                "an existing document."
            )

        return DocumentReplacementResult(
            document_id=normalized_document_id,
            old_deleted_chunk_count=(
                deletion.deleted_chunk_count
            ),
            old_deleted_hash_count=(
                deletion.deleted_hash_count
            ),
            content_hash=ingestion.content_hash,
            chunk_count=ingestion.chunk_count,
        )
