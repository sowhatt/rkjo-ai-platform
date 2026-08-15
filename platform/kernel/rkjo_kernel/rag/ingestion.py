from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from rkjo_kernel.rag.deduplication import DocumentHashRegistry
from rkjo_kernel.rag.hashing import compute_content_hash
from rkjo_kernel.rag.ingestion_models import IngestionResult
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

    def ingest_file(
        self,
        path: str | Path,
        *,
        document_id: str | None = None,
        metadata: dict | None = None,
    ) -> IngestionResult:
        loaded = self.loader.load(path)

        sanitized = self.sanitizer.sanitize(
            loaded.content
        )

        if not sanitized.content.strip():
            raise ValueError(
                "Sanitization removed all document content."
            )

        # Hash the SAFE content, not the raw source.
        content_hash = compute_content_hash(
            sanitized.content
        )

        resolved_document_id = (
            document_id
            or str(uuid4())
        )

        if self.hash_registry.contains(
            content_hash
        ):
            return IngestionResult(
                document_id=resolved_document_id,
                content_hash=content_hash,
                chunk_count=0,
                duplicate=True,
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

        chunk_count = self.retriever.ingest(
            document
        )

        self.hash_registry.register(
            content_hash=content_hash,
            document_id=resolved_document_id,
        )

        return IngestionResult(
            document_id=resolved_document_id,
            content_hash=content_hash,
            chunk_count=chunk_count,
            duplicate=False,
        )
