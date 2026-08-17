from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from rkjo_kernel.rag.deduplication import DocumentHashRegistry
from rkjo_kernel.rag.hashing import compute_content_hash
from rkjo_kernel.rag.ingestion_models import (
    IngestionResult,
    PreparedChunk,
    PreparedIngestion,
)
from rkjo_kernel.rag.loaders import CompositeDocumentLoader
from rkjo_kernel.rag.models import Document
from rkjo_kernel.rag.privacy import (
    DocumentSanitizer,
    NoOpDocumentSanitizer,
)
from rkjo_kernel.rag.retriever import Retriever


class DocumentIngestionPipeline:

    def __init__(
        self,
        *,
        loader: CompositeDocumentLoader,
        retriever: Retriever,
        hash_registry: DocumentHashRegistry,
        sanitizer: DocumentSanitizer | None = None,
    ) -> None:
        self.loader = loader
        self.retriever = retriever
        self.hash_registry = hash_registry
        self.sanitizer = (
            sanitizer
            or NoOpDocumentSanitizer()
        )

    def prepare_file(
        self,
        path: str | Path,
        *,
        document_id: str | None = None,
        metadata: dict | None = None,
    ) -> PreparedIngestion:
        """Prepare sanitized chunks and embeddings without DB writes."""

        loaded = self.loader.load(path)

        sanitized = self.sanitizer.sanitize(
            loaded.content
        )

        if not sanitized.content.strip():
            raise ValueError(
                "Sanitization removed all document content."
            )

        content_hash = compute_content_hash(
            sanitized.content
        )

        resolved_document_id = (
            document_id
            or str(uuid4())
        )

        merged_metadata = {
            **loaded.metadata,
            **(metadata or {}),
            "source_path": str(
                loaded.source_path
            ),
            "source_type": loaded.source_type,
            "content_hash": content_hash,
            "sanitization_mode": (
                sanitized.mode.value
            ),
            "pii_detection_count": (
                sanitized.detection_count
            ),
            "pii_categories": list(
                sanitized.categories
            ),
        }

        document = Document(
            document_id=resolved_document_id,
            content=sanitized.content,
            metadata=merged_metadata,
        )

        chunks = self.retriever.chunker.split(
            document
        )

        prepared_chunks = []

        # Every embedding is computed BEFORE any persistent
        # modification is allowed to happen.
        for chunk in chunks:
            embedding = (
                self.retriever
                .embedding_provider
                .embed(chunk.content)
            )

            prepared_chunks.append(
                PreparedChunk(
                    chunk=chunk,
                    embedding=tuple(
                        float(value)
                        for value in embedding
                    ),
                )
            )

        return PreparedIngestion(
            document_id=resolved_document_id,
            content_hash=content_hash,
            chunks=tuple(prepared_chunks),
        )

    def ingest_file(
        self,
        path: str | Path,
        *,
        document_id: str | None = None,
        metadata: dict | None = None,
    ) -> IngestionResult:
        prepared = self.prepare_file(
            path,
            document_id=document_id,
            metadata=metadata,
        )

        if self.hash_registry.contains(
            prepared.content_hash
        ):
            return IngestionResult(
                document_id=prepared.document_id,
                content_hash=prepared.content_hash,
                chunk_count=0,
                duplicate=True,
            )

        for prepared_chunk in prepared.chunks:
            self.retriever.vector_store.add(
                chunk=prepared_chunk.chunk,
                embedding=list(
                    prepared_chunk.embedding
                ),
            )

        self.hash_registry.register(
            content_hash=prepared.content_hash,
            document_id=prepared.document_id,
        )

        return IngestionResult(
            document_id=prepared.document_id,
            content_hash=prepared.content_hash,
            chunk_count=prepared.chunk_count,
            duplicate=False,
        )
