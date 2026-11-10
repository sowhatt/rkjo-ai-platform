"""MM-RAG-02.3: OCR provenance and pre-embedding privacy boundaries."""
from dataclasses import dataclass

import pytest

from rkjo_kernel.rag.chunking import TextChunker
from rkjo_kernel.rag.evidence_ingestion import EvidenceRAGIngestion
from rkjo_kernel.rag.models import RetrievedChunk
from rkjo_kernel.rag.multimodal_evidence import (
    EvidenceBlock, EvidenceDocument, EvidenceKind, EvidenceLocation, ExtractionMethod,
)
from rkjo_kernel.rag.multimodal_ocr import MixedPDFExtraction
from rkjo_kernel.rag.retriever import Retriever


class EmbeddingSpy:
    def __init__(self):
        self.texts = []

    def embed(self, content):
        self.texts.append(content)
        return [0.1, 0.2, 0.3]


class InMemoryStore:
    def __init__(self):
        self.writes = []

    def add(self, *, chunk, embedding):
        self.writes.append((chunk, embedding))

    def search(self, *, query_embedding, limit=5, filters=None):
        return [
            RetrievedChunk(chunk=chunk, score=0.9)
            for chunk, embedding in self.writes
            if filters is None or filters.matches(chunk.metadata)
        ][:limit]


def example(*, tenant="t1", complete=True):
    blocks = (
        EvidenceBlock(
            block_id="p1-ocr", kind=EvidenceKind.TEXT,
            text="Optique 250 euros. Contact: client@example.com",
            extraction_method=ExtractionMethod.OCR,
            location=EvidenceLocation(page_number=1),
        ),
        EvidenceBlock(
            block_id="p2-text", kind=EvidenceKind.TEXT,
            text="Dentaire 400 euros.",
            extraction_method=ExtractionMethod.NATIVE_TEXT,
            location=EvidenceLocation(page_number=2),
        ),
    )
    return MixedPDFExtraction(
        document=EvidenceDocument(tenant_id=tenant, document_id="contrat-1",
                                  source_type="pdf", blocks=blocks),
        page_count=3 if not complete else 2,
        ocr_pages=(1,), rejected_pages=() if complete else (3,),
    )


def service():
    embeddings = EmbeddingSpy()
    store = InMemoryStore()
    retriever = Retriever(
        chunker=TextChunker(chunk_size=200, overlap=20),
        embedding_provider=embeddings, vector_store=store,
    )
    return EvidenceRAGIngestion(retriever=retriever), embeddings, store


def test_ocr_pages_are_indexed_separately_with_citations():
    bridge, embeds, store = service()
    prepared = bridge.ingest(example(), tenant_id="t1")
    assert len(prepared.chunks) == 2
    assert len(store.writes) == 2
    first = store.writes[0][0]
    second = store.writes[1][0]
    assert first.metadata["page_number"] == 1
    assert second.metadata["page_number"] == 2
    assert first.metadata["extraction_method"] == "ocr"
    assert second.metadata["extraction_method"] == "native_text"
    assert first.metadata["evidence_document_id"] == "contrat-1"
    assert first.metadata["tenant_id"] == "t1"
    assert "[EMAIL]" in first.content
    assert "client@example.com" not in repr(embeds.texts)
    assert "client@example.com" not in repr(first.metadata)


def test_tenant_rejected_before_embedding_or_storage():
    bridge, embeds, store = service()
    with pytest.raises(PermissionError):
        bridge.ingest(example(tenant="t2"), tenant_id="t1")
    assert embeds.texts == []
    assert store.writes == []


def test_incomplete_ocr_rejected_before_embedding_or_storage():
    bridge, embeds, store = service()
    with pytest.raises(ValueError, match="Incomplete"):
        bridge.ingest(example(complete=False), tenant_id="t1")
    assert embeds.texts == []
    assert store.writes == []


def test_prepare_only_never_writes():
    bridge, _, store = service()
    prepared = bridge.prepare(example(), tenant_id="t1")
    assert len(prepared.chunks) == 2
    assert store.writes == []


def test_retrieval_filters_are_tenant_and_document_scoped():
    bridge, _, store = service()
    bridge.ingest(example(), tenant_id="t1")
    correct = bridge.filters(tenant_id="t1", document_id="contrat-1")
    wrong = bridge.filters(tenant_id="t2")
    assert len(store.search(query_embedding=[0.1, 0.2, 0.3], filters=correct)) == 2
    assert store.search(query_embedding=[0.1, 0.2, 0.3], filters=wrong) == []


def test_text_chunks_never_cross_page_boundaries():
    bridge, _, store = service()
    bridge.ingest(example(), tenant_id="t1")
    assert all(
        ("Optique" in chunk.content) != ("Dentaire" in chunk.content)
        for chunk, embedding in store.writes
    )


def test_document_filter_requires_value():
    with pytest.raises(ValueError):
        EvidenceRAGIngestion.filters(tenant_id="t1", document_id="")
    with pytest.raises(ValueError):
        EvidenceRAGIngestion.filters(tenant_id="")
