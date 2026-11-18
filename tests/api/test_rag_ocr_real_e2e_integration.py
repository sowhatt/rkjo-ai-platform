"""MM-RAG-02.6 real PDF -> HTTP -> local OCR -> PostgreSQL -> search -> answer.

Uses a dedicated temporary pgvector table and a synthetic raster-only PDF.
No OpenAI requests. Runs only when PostgreSQL, Poppler, Tesseract and Pillow
are available; inspect -rs for skips (skips are NOT passing E2E evidence).
"""
from __future__ import annotations

import io
import os
import shutil
from uuid import uuid4

import psycopg
import pytest

from rkjo_api.dependencies import get_rag_answering_service, get_rag_search_service
from rkjo_api.main import app
from rkjo_api.rag_ocr import get_ocr_ingestion_service, OCRUploadResult
from rkjo_kernel.rag.chunking import TextChunker
from rkjo_kernel.rag.embedding import DeterministicEmbeddingProvider
from rkjo_kernel.rag.evidence_ingestion import EvidenceRAGIngestion
from rkjo_kernel.rag.local_pdf_ocr import LocalTesseractPDFOCR
from rkjo_kernel.rag.multimodal_ocr import MixedPDFEvidenceExtractor
from rkjo_kernel.rag.postgres_evidence_publisher import PostgresEvidencePublisher
from rkjo_kernel.rag.postgres_vector_store import PostgresPgVectorStore
from rkjo_kernel.rag.rag_answering import RAGAnsweringService
from rkjo_kernel.rag.retriever import Retriever
from rkjo_kernel.rag.semantic_search import SemanticSearchService
from rkjo_kernel.rag.privacy import RuleBasedPIISanitizer


DB = os.getenv("RKJO_TEST_DATABASE_URL", "")


def prerequisites_available():
    if not DB or not all(shutil.which(cmd) for cmd in ("pdftoppm", "tesseract")):
        return False
    try:
        with psycopg.connect(DB, connect_timeout=2) as conn:
            return conn.execute("SELECT 1").fetchone() == (1,)
    except psycopg.Error:
        return False


pytestmark = pytest.mark.skipif(
    not prerequisites_available(),
    reason="E2E requires RKJO_TEST_DATABASE_URL, PostgreSQL, Poppler and Tesseract",
)


class SyntheticAnswerGenerator:
    """No LLM network call: tests retrieval grounding and citation plumbing."""
    def generate(self, *, question, context):
        if "250 euros" not in context:
            raise AssertionError("Expected evidence missing from retrieved context.")
        return "Le contrat prévoit une garantie optique de 250 euros [1]."


class RealOCRService:
    def __init__(self, store, retriever):
        self.store = store
        self.retriever = retriever
        self.publisher = PostgresEvidencePublisher(
            database_url=DB, table_name=store.table_name,
        )

    def ingest(self, path, *, tenant_id, document_id):
        extraction = MixedPDFEvidenceExtractor(
            LocalTesseractPDFOCR(language="fra+eng")
        ).extract(path, tenant_id=tenant_id, document_id=document_id)
        prepared = EvidenceRAGIngestion(retriever=self.retriever).prepare(
            extraction, tenant_id=tenant_id,
        )
        inserted = self.publisher.publish(prepared, tenant_id=tenant_id)
        return OCRUploadResult(
            document_id=document_id, page_count=extraction.page_count,
            ocr_pages=list(extraction.ocr_pages), chunk_count=inserted,
            content_hash=prepared.content_hash,
        )


@pytest.fixture
def real_pipeline(monkeypatch):
    monkeypatch.setenv("RKJO_RAG_OCR_API_ENABLED", "true")
    table = "rag_ocr_e2e_" + uuid4().hex
    store = PostgresPgVectorStore(database_url=DB, dimensions=16, table_name=table)
    store.initialize_schema()
    retriever = Retriever(
        chunker=TextChunker(chunk_size=1000, overlap=150),
        embedding_provider=DeterministicEmbeddingProvider(dimensions=16),
        vector_store=store,
    )
    search = SemanticSearchService(
        retriever=retriever, sanitizer=RuleBasedPIISanitizer(),
    )
    app.dependency_overrides[get_ocr_ingestion_service] = lambda: RealOCRService(store, retriever)
    app.dependency_overrides[get_rag_search_service] = lambda: search
    app.dependency_overrides[get_rag_answering_service] = lambda: RAGAnsweringService(
        search_service=search, generator=SyntheticAnswerGenerator(),
    )
    try:
        yield store
    finally:
        for dep in (get_ocr_ingestion_service, get_rag_search_service, get_rag_answering_service):
            app.dependency_overrides.pop(dep, None)
        store.drop_schema()


@pytest.fixture
def scanned_pdf_bytes():
    image_module = pytest.importorskip("PIL.Image")
    draw_module = pytest.importorskip("PIL.ImageDraw")
    font_module = pytest.importorskip("PIL.ImageFont")
    image = image_module.new("RGB", (1600, 900), "white")
    draw = draw_module.Draw(image)
    try:
        font = font_module.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 46)
    except OSError:
        font = font_module.truetype("DejaVuSans.ttf", 46)
    for index, line in enumerate((
        "CONTRAT MUTUELLE SANTE 2026",
        "Garantie optique : 250 euros",
        "Garantie dentaire : 400 euros",
        "Hospitalisation : 100 pour cent",
    )):
        draw.text((80, 100 + index * 140), line, fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PDF", resolution=150)
    return buffer.getvalue()


def test_real_scanned_pdf_http_to_pgvector_and_answer(
    client, real_pipeline, scanned_pdf_bytes, monkeypatch,
):
    operator = {"X-API-Key": "rkjo-operator-key"}
    viewer = {"X-API-Key": "rkjo-viewer-key"}
    document_id = "synthetic-" + uuid4().hex

    uploaded = client.post(
        "/rag/ocr/documents", headers=operator,
        files={"file": ("garanties_scannes.pdf", scanned_pdf_bytes, "application/pdf")},
        data={"document_id": document_id},
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["ocr_pages"] == [1]
    assert uploaded.json()["page_count"] == 1
    assert uploaded.json()["chunk_count"] >= 1

    searched = client.post(
        "/rag/search", headers=viewer,
        json={"query": "Garantie optique 250 euros", "limit": 5},
    )
    assert searched.status_code == 200, searched.text
    assert searched.json()["results"]
    assert all(row["metadata"]["tenant_id"] == "tenant-a" for row in searched.json()["results"])
    assert any(
        row["metadata"]["page_number"] == 1 and row["metadata"]["extraction_method"] == "ocr"
        for row in searched.json()["results"]
    )

    answered = client.post(
        "/rag/answer", headers=viewer,
        json={"question": "Quelle est la garantie optique ?", "limit": 5},
    )
    assert answered.status_code == 200, answered.text
    assert "250 euros" in answered.json()["answer"]
    assert answered.json()["sources"][0]["page_number"] == 1
    assert answered.json()["sources"][0]["document_id"] == document_id

    # Switch the authenticated viewer to another tenant: no OCR data leak.
    monkeypatch.setenv("RKJO_VIEWER_TENANT_ID", "tenant-b")
    denied = client.post(
        "/rag/search", headers=viewer,
        json={"query": "Garantie optique 250 euros"},
    )
    assert denied.status_code == 200
    assert denied.json()["result_count"] == 0

    # Different tenant must not replace the existing document ID.
    monkeypatch.setenv("RKJO_OPERATOR_TENANT_ID", "tenant-b")
    clash = client.post(
        "/rag/ocr/documents", headers=operator,
        files={"file": ("garanties_scannes.pdf", scanned_pdf_bytes, "application/pdf")},
        data={"document_id": document_id},
    )
    assert clash.status_code == 403
    assert real_pipeline.count() >= 1
