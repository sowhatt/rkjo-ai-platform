"""MM-RAG-02.4 PostgreSQL atomic evidence publication integration tests."""
import os
from uuid import uuid4

import psycopg
import pytest

from rkjo_kernel.rag.chunking import TextChunker
from rkjo_kernel.rag.embedding import DeterministicEmbeddingProvider
from rkjo_kernel.rag.evidence_ingestion import EvidenceRAGIngestion
from rkjo_kernel.rag.multimodal_evidence import (
    EvidenceBlock, EvidenceDocument, EvidenceKind, EvidenceLocation, ExtractionMethod,
)
from rkjo_kernel.rag.multimodal_ocr import MixedPDFExtraction
from rkjo_kernel.rag.postgres_evidence_publisher import PostgresEvidencePublisher
from rkjo_kernel.rag.postgres_vector_store import PostgresPgVectorStore
from rkjo_kernel.rag.retriever import Retriever


URL = os.getenv("RKJO_TEST_DATABASE_URL", "postgresql://rkjo:rkjo_password@localhost:5432/rkjo")
def available():
    try:
        with psycopg.connect(URL, connect_timeout=2):
            return True
    except psycopg.Error:
        return False


pytestmark = pytest.mark.skipif(not available(), reason="Test PostgreSQL unavailable")


@pytest.fixture
def system():
    table = "rag_evidence_test_" + uuid4().hex
    store = PostgresPgVectorStore(database_url=URL, dimensions=16, table_name=table)
    store.initialize_schema()
    provider = DeterministicEmbeddingProvider(dimensions=16)
    retriever = Retriever(chunker=TextChunker(chunk_size=200, overlap=20),
                          embedding_provider=provider, vector_store=store)
    bridge = EvidenceRAGIngestion(retriever=retriever)
    publisher = PostgresEvidencePublisher(database_url=URL, table_name=table)
    yield store, bridge, publisher, provider
    store.drop_schema()


def extraction(tenant, document="policy-2026", *, text="Optique 250 euros", pages=2):
    blocks = tuple(EvidenceBlock(
        block_id=f"p{i}-ocr", kind=EvidenceKind.TEXT,
        text=f"{text} page {i}", extraction_method=ExtractionMethod.OCR,
        location=EvidenceLocation(page_number=i),
    ) for i in range(1, pages + 1))
    return MixedPDFExtraction(
        document=EvidenceDocument(tenant_id=tenant, document_id=document,
                                  source_type="pdf", blocks=blocks),
        page_count=pages, ocr_pages=tuple(range(1, pages + 1)), rejected_pages=(),
    )


def test_atomic_publish_search_and_replace(system):
    store, bridge, publisher, provider = system
    first = bridge.prepare(extraction("tenant-a"), tenant_id="tenant-a")
    assert publisher.publish(first, tenant_id="tenant-a") == 2
    results = store.search(
        query_embedding=provider.embed("Optique 250 euros"),
        limit=5, filters=bridge.filters(tenant_id="tenant-a", document_id="policy-2026"),
    )
    assert {r.chunk.metadata["page_number"] for r in results} == {1, 2}
    assert all(r.chunk.metadata["extraction_method"] == "ocr" for r in results)
    assert store.search(
        query_embedding=provider.embed("Optique 250 euros"),
        filters=bridge.filters(tenant_id="tenant-b"),
    ) == []
    replacement = bridge.prepare(
        extraction("tenant-a", text="Dentaire 400 euros", pages=1),
        tenant_id="tenant-a",
    )
    publisher.publish(replacement, tenant_id="tenant-a")
    assert store.count() == 1
    assert store.search(
        query_embedding=provider.embed("Dentaire 400 euros"),
        filters=bridge.filters(tenant_id="tenant-a"),
    )[0].chunk.metadata["page_number"] == 1


def test_cross_tenant_document_id_collision_is_denied(system):
    store, bridge, publisher, _ = system
    publisher.publish(bridge.prepare(extraction("tenant-a"), tenant_id="tenant-a"),
                      tenant_id="tenant-a")
    other = bridge.prepare(extraction("tenant-b"), tenant_id="tenant-b")
    with pytest.raises(PermissionError, match="different tenant"):
        publisher.publish(other, tenant_id="tenant-b")
    assert store.count() == 2


def test_rollback_when_later_chunk_conflicts(system):
    store, bridge, publisher, _ = system
    original = bridge.prepare(extraction("tenant-a", pages=2), tenant_id="tenant-a")
    publisher.publish(original, tenant_id="tenant-a")
    replacement = bridge.prepare(
        extraction("tenant-a", text="New value", pages=2), tenant_id="tenant-a",
    )
    # A conflict within this same batch occurs on the second INSERT.
    from dataclasses import replace
    from rkjo_kernel.rag.ingestion_models import PreparedChunk
    from rkjo_kernel.rag.models import DocumentChunk
    second = replacement.chunks[1]
    duplicate = replace(second.chunk, chunk_id=replacement.chunks[0].chunk.chunk_id)
    modified = replace(replacement, chunks=(
        replacement.chunks[0], PreparedChunk(chunk=duplicate, embedding=second.embedding),
    ))
    with pytest.raises(psycopg.errors.UniqueViolation):
        publisher.publish(modified, tenant_id="tenant-a")
    assert store.count() == 2
    with psycopg.connect(URL) as conn:
        rows = conn.execute(
            f'SELECT content FROM "{store.table_name}" ORDER BY chunk_index',
        ).fetchall()
    assert all("Optique" in row[0] for row in rows)


def test_publisher_rejects_wrong_authorized_tenant(system):
    store, bridge, publisher, _ = system
    prepared = bridge.prepare(extraction("tenant-a"), tenant_id="tenant-a")
    with pytest.raises(PermissionError):
        publisher.publish(prepared, tenant_id="tenant-b")
    assert store.count() == 0
