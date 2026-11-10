"""MM-RAG-02.3: tenant-scoped, citation-preserving evidence ingestion.

Prepare embeddings after PII sanitization; persist only complete documents.
Caller must authenticate/authorize the tenant and supply its scoped store.
"""
from __future__ import annotations

from dataclasses import dataclass

from rkjo_kernel.rag.chunking import TextChunker
from rkjo_kernel.rag.hashing import compute_content_hash
from rkjo_kernel.rag.ingestion_models import PreparedChunk
from rkjo_kernel.rag.models import Document
from rkjo_kernel.rag.multimodal_evidence import EvidenceDocument
from rkjo_kernel.rag.multimodal_ocr import MixedPDFExtraction
from rkjo_kernel.rag.privacy import DocumentSanitizer, RuleBasedPIISanitizer
from rkjo_kernel.rag.retriever import Retriever
from rkjo_kernel.rag.retrieval_filters import RetrievalFilters


@dataclass(frozen=True, slots=True)
class PreparedEvidence:
    tenant_id: str
    document_id: str
    chunks: tuple[PreparedChunk, ...]
    content_hash: str


class EvidenceRAGIngestion:
    """Isolated opt-in bridge; does not modify legacy /rag/documents.

    This stage does not persist raw scanned PDFs. Each block is chunked
    independently, so no chunk can cross pages or merge OCR/native citations.
    """

    def __init__(
        self, *, retriever: Retriever,
        sanitizer: DocumentSanitizer | None = None,
    ) -> None:
        self.retriever = retriever
        self.sanitizer = sanitizer if sanitizer is not None else RuleBasedPIISanitizer()

    def prepare(
        self, extraction: MixedPDFExtraction, *, tenant_id: str,
    ) -> PreparedEvidence:
        document = extraction.document
        if not tenant_id.strip() or document.tenant_id != tenant_id:
            raise PermissionError("Evidence tenant does not match authorized tenant.")
        if not extraction.complete:
            raise ValueError("Incomplete OCR evidence cannot be indexed.")
        if document.source_type != "pdf" or not document.blocks:
            raise ValueError("Only nonempty PDF evidence is supported.")
        prepared: list[PreparedChunk] = []
        normalized: list[str] = []
        next_index = 0
        for block in document.searchable_blocks():
            sanitized = self.sanitizer.sanitize(block.text)
            if not sanitized.content.strip():
                raise ValueError("PII sanitization removed all page evidence.")
            citation = document.citation(block.block_id, tenant_id=tenant_id)
            metadata = {
                "tenant_id": tenant_id,
                "evidence_document_id": document.document_id,
                "source_type": document.source_type,
                "evidence_block_id": block.block_id,
                "page_number": citation["page_number"],
                "extraction_method": citation["extraction_method"],
                "evidence_kind": citation["kind"],
                "extraction_version": document.extraction_version,
                "sanitization_mode": sanitized.mode.value,
                "pii_detection_count": sanitized.detection_count,
                "pii_categories": list(sanitized.categories),
            }
            # No original OCR text is placed in metadata.
            chunks = self.retriever.chunker.split(Document(
                document_id=document.document_id,
                content=sanitized.content,
                metadata=metadata,
            ))
            normalized.append(sanitized.content)
            for chunk in chunks:
                from rkjo_kernel.rag.models import DocumentChunk
                indexed_chunk = DocumentChunk(
                    document_id=chunk.document_id,
                    chunk_id=chunk.chunk_id,
                    chunk_index=next_index,
                    content=chunk.content,
                    metadata=chunk.metadata,
                )
                next_index += 1
                embedding = self.retriever.embedding_provider.embed(indexed_chunk.content)
                prepared.append(PreparedChunk(
                    chunk=indexed_chunk,
                    embedding=tuple(float(value) for value in embedding),
                ))
        if not prepared:
            raise ValueError("No searchable evidence to index.")
        return PreparedEvidence(
            tenant_id=tenant_id,
            document_id=document.document_id,
            chunks=tuple(prepared),
            content_hash=compute_content_hash("\n".join(normalized)),
        )

    def ingest(self, extraction: MixedPDFExtraction, *, tenant_id: str) -> PreparedEvidence:
        """Write prepared chunks using the configured store.

        For production, wrap this call in a document-scoped transaction or
        stage-and-swap protocol: VectorStore.add is not atomic over a document.
        """
        prepared = self.prepare(extraction, tenant_id=tenant_id)
        for item in prepared.chunks:
            self.retriever.vector_store.add(
                chunk=item.chunk, embedding=list(item.embedding),
            )
        return prepared

    @staticmethod
    def filters(*, tenant_id: str, document_id: str | None = None) -> RetrievalFilters:
        if not tenant_id.strip():
            raise ValueError("Tenant filter is required.")
        metadata = {"tenant_id": tenant_id}
        if document_id is not None:
            if not document_id.strip():
                raise ValueError("Document ID must not be empty.")
            metadata["evidence_document_id"] = document_id
        return RetrievalFilters(metadata=metadata)
