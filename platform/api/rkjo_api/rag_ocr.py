"""Opt-in, authenticated PDF OCR ingestion API. Disabled by default."""
from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from rkjo_api.dependencies import (
    get_database_url, get_embedding_dimensions, get_embedding_space,
    get_education_course_service,
)
from rkjo_education.course.service import CourseService
from rkjo_api.identity import get_authenticated_identity
from rkjo_api.rag import MAX_UPLOAD_BYTES, persist_upload_temporarily
from rkjo_kernel.rag.chunking import TextChunker
from rkjo_kernel.rag.embedding_factory import build_embedding_provider
from rkjo_kernel.rag.evidence_ingestion import EvidenceRAGIngestion
from rkjo_kernel.rag.local_pdf_ocr import LocalTesseractPDFOCR
from rkjo_kernel.rag.multimodal_ocr import MixedPDFEvidenceExtractor
from rkjo_kernel.rag.postgres_evidence_publisher import PostgresEvidencePublisher
from rkjo_kernel.rag.postgres_vector_store import PostgresPgVectorStore
from rkjo_kernel.rag.retriever import Retriever


router = APIRouter(prefix="/rag/ocr", tags=["rag-ocr"])


class OCRUploadResult(BaseModel):
    document_id: str
    page_count: int
    ocr_pages: list[int]
    chunk_count: int
    content_hash: str


class OCRIngestionService:
    def ingest(self, path: Path, *, tenant_id: str, document_id: str) -> OCRUploadResult:
        extracted = MixedPDFEvidenceExtractor(LocalTesseractPDFOCR()).extract(
            path, tenant_id=tenant_id, document_id=document_id,
        )
        store = PostgresPgVectorStore(
            database_url=get_database_url(), dimensions=get_embedding_dimensions(),
            embedding_space=get_embedding_space(),
        )
        store.initialize_schema()
        bridge = EvidenceRAGIngestion(retriever=Retriever(
            chunker=TextChunker(chunk_size=1000, overlap=150),
            embedding_provider=build_embedding_provider(),
            vector_store=store,
        ))
        prepared = bridge.prepare(extracted, tenant_id=tenant_id)
        publisher = PostgresEvidencePublisher(
            database_url=get_database_url(),
            embedding_space=get_embedding_space(),
        )
        count = publisher.publish(prepared, tenant_id=tenant_id)
        return OCRUploadResult(
            document_id=document_id, page_count=extracted.page_count,
            ocr_pages=list(extracted.ocr_pages), chunk_count=count,
            content_hash=prepared.content_hash,
        )


def get_ocr_ingestion_service() -> OCRIngestionService:
    return OCRIngestionService()


@router.post("/documents", response_model=OCRUploadResult, status_code=201)
async def ingest_scanned_pdf(
    request: Request,
    file: UploadFile = File(...),
    document_id: str | None = Form(default=None),
    service: OCRIngestionService = Depends(get_ocr_ingestion_service),
) -> OCRUploadResult:
    if os.getenv("RKJO_RAG_OCR_API_ENABLED", "").lower() != "true":
        raise HTTPException(status_code=404, detail="OCR ingestion not enabled.")
    identity = get_authenticated_identity(request)
    if not identity.tenant_id or not identity.tenant_id.strip():
        raise HTTPException(status_code=403, detail="Tenant-bound identity required.")
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF OCR ingestion is supported.")
    resolved_id = document_id or str(uuid4())
    if not resolved_id.strip() or len(resolved_id) > 200:
        raise HTTPException(status_code=422, detail="Invalid document identifier.")
    temporary = await persist_upload_temporarily(file)
    try:
        # Header check: do not send arbitrary uploaded payloads to Poppler.
        with temporary.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise HTTPException(status_code=422, detail="Invalid PDF signature.")
        try:
            return service.ingest(
                temporary, tenant_id=identity.tenant_id, document_id=resolved_id,
            )
        except PermissionError:
            raise HTTPException(status_code=403, detail="Document access denied.") from None
        except ValueError:
            raise HTTPException(status_code=422, detail="Unable to process PDF evidence.") from None
    finally:
        temporary.unlink(missing_ok=True)


@router.post("/courses/{course_id}/documents", response_model=OCRUploadResult, status_code=201)
async def ingest_course_scanned_pdf(
    course_id: str,
    request: Request,
    file: UploadFile = File(...),
    service: OCRIngestionService = Depends(get_ocr_ingestion_service),
    courses: CourseService = Depends(get_education_course_service),
) -> OCRUploadResult:
    """OCR for an existing course, bound to the authenticated tenant.

    This endpoint is still feature-gated and not exposed to public web clients.
    """
    if os.getenv("RKJO_RAG_OCR_API_ENABLED", "").lower() != "true":
        raise HTTPException(status_code=404, detail="OCR ingestion not enabled.")
    identity = get_authenticated_identity(request)
    tenant_id = identity.tenant_id
    if not tenant_id or not tenant_id.strip():
        raise HTTPException(status_code=403, detail="Tenant-bound identity required.")
    if not course_id.strip() or len(course_id) > 200:
        raise HTTPException(status_code=422, detail="Invalid course identifier.")
    try:
        courses.get(tenant_id=tenant_id, course_id=course_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Course not found.") from None
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF OCR ingestion is supported.")
    # Generated IDs avoid allowing users to overwrite an unrelated document.
    document_id = "education-" + str(uuid4())
    temporary = await persist_upload_temporarily(file)
    try:
        with temporary.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise HTTPException(status_code=422, detail="Invalid PDF signature.")
        try:
            result = service.ingest(
                temporary, tenant_id=tenant_id, document_id=document_id,
            )
        except PermissionError:
            raise HTTPException(status_code=403, detail="Document access denied.") from None
        except ValueError:
            raise HTTPException(status_code=422, detail="Unable to process PDF evidence.") from None
        # Association follows committed indexation. Failure needs compensating
        # cleanup in a future cross-service transaction/outbox workflow.
        courses.attach_document(
            tenant_id=tenant_id, course_id=course_id, document_id=document_id,
        )
        return result
    finally:
        temporary.unlink(missing_ok=True)
