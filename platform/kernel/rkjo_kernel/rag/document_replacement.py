"""RAG document replacement and reindexing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rkjo_kernel.rag.ingestion import (
    DocumentIngestionPipeline,
)
from rkjo_kernel.rag.postgres_document_replacement import (
    PostgresDocumentReplacementRepository,
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
    """Prepare then atomically replace one RAG document."""

    def __init__(
        self,
        *,
        ingestion_pipeline: DocumentIngestionPipeline,
        replacement_repository: (
            PostgresDocumentReplacementRepository
        ),
    ) -> None:
        self.ingestion_pipeline = ingestion_pipeline
        self.replacement_repository = (
            replacement_repository
        )

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

        # Load, sanitize, chunk and EMBED first.
        # No persistent state has changed yet.
        prepared = (
            self.ingestion_pipeline.prepare_file(
                path,
                document_id=normalized_document_id,
                metadata=metadata,
            )
        )

        # Only after successful preparation do we enter
        # the atomic PostgreSQL swap.
        deleted = (
            self.replacement_repository.replace(
                prepared,
                filters=filters,
            )
        )

        if deleted is None:
            return None

        (
            deleted_chunks,
            deleted_hashes,
        ) = deleted

        return DocumentReplacementResult(
            document_id=prepared.document_id,
            old_deleted_chunk_count=(
                deleted_chunks
            ),
            old_deleted_hash_count=(
                deleted_hashes
            ),
            content_hash=prepared.content_hash,
            chunk_count=prepared.chunk_count,
        )
