"""Learner-first Education ingestion and referential alignment API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from rkjo_api.education import require_uuid_tenant
from rkjo_api.dependencies import get_database_url
from rkjo_education.alignment import ReferentialCompetency
from rkjo_education.ingestion import DocumentKind, EducationIngestionService, Provenance
from rkjo_education.ingestion.extractor import DocumentExtractionError, EducationDocumentExtractor
from rkjo_education.ingestion.postgres_repository import PostgresEducationDocumentRepository, StoredQuestionAlignment
from rkjo_education.ingestion.aligned_copy import CorrectedCopyAlignmentService


router = APIRouter(prefix="/education", tags=["education-ingestion"])


class ReferentialCompetencyRequest(BaseModel):
    code: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=255)
    keywords: list[str] = Field(default_factory=list)
    importance: int = Field(default=1, ge=1, le=3)


class AnalyzeDocumentRequest(BaseModel):
    learner_id: UUID
    filename: str = Field(min_length=1, max_length=300)
    media_type: str = Field(min_length=1, max_length=200)
    extracted_text: str = Field(min_length=1)
    kind: DocumentKind
    provenance: Provenance = Provenance.LEARNER_UPLOAD
    referential: list[ReferentialCompetencyRequest] = Field(default_factory=list)


class QuestionAlignmentResponse(BaseModel):
    question_ref: str
    competency_code: str | None
    alignment_confidence: float
    requires_confirmation: bool
    earned_points: float | None = None
    max_points: float | None = None


class AnalyzeDocumentResponse(BaseModel):
    document_id: UUID
    source_hash: str
    kind: DocumentKind
    provenance: Provenance
    questions: list[QuestionAlignmentResponse]


@router.post("/documents/analyze", response_model=AnalyzeDocumentResponse)
def analyze_document(payload: AnalyzeDocumentRequest, request: Request) -> AnalyzeDocumentResponse:
    tenant_id = require_uuid_tenant(request)
    try:
        document = EducationIngestionService().ingest(
            tenant_id=tenant_id,
            learner_id=payload.learner_id,
            filename=payload.filename,
            media_type=payload.media_type,
            extracted_text=payload.extracted_text,
            kind=payload.kind,
            provenance=payload.provenance,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    questions: list[QuestionAlignmentResponse] = []
    if payload.kind == DocumentKind.CORRECTED_COPY:
        referential = [
            ReferentialCompetency(
                code=item.code,
                label=item.label,
                keywords=tuple(item.keywords),
                importance=item.importance,
            )
            for item in payload.referential
        ]
        rows = CorrectedCopyAlignmentService().process(
            text=document.extracted_text,
            referential=referential,
            source_id=document.id,
        )
        questions = [
            QuestionAlignmentResponse(
                question_ref=row.question_ref,
                competency_code=row.competency_code,
                alignment_confidence=row.alignment_confidence,
                requires_confirmation=row.requires_confirmation,
                earned_points=(row.evidence.earned_points if row.evidence else None),
                max_points=(row.evidence.max_points if row.evidence else None),
            )
            for row in rows
        ]

    return AnalyzeDocumentResponse(
        document_id=document.id,
        source_hash=document.source_hash,
        kind=document.kind,
        provenance=document.provenance,
        questions=questions,
    )


@router.post("/documents/upload", response_model=AnalyzeDocumentResponse)
async def upload_document(
    request: Request,
    learner_id: UUID = Form(...),
    kind: DocumentKind = Form(...),
    file: UploadFile = File(...),
) -> AnalyzeDocumentResponse:
    tenant_id = require_uuid_tenant(request)
    content = await file.read()
    try:
        extracted_text = EducationDocumentExtractor().extract(
            filename=file.filename or "document",
            media_type=file.content_type or "application/octet-stream",
            content=content,
        )
        document = EducationIngestionService().ingest(
            tenant_id=tenant_id,
            learner_id=learner_id,
            filename=file.filename or "document",
            media_type=file.content_type or "application/octet-stream",
            extracted_text=extracted_text,
            kind=kind,
            provenance=Provenance.LEARNER_UPLOAD,
        )
    except (DocumentExtractionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    questions: list[QuestionAlignmentResponse] = []
    if kind == DocumentKind.CORRECTED_COPY:
        # Temporary demo referential. J4 persistence will replace this with
        # the learner/course referential resolved from the Education domain.
        demo_referential = [
            ReferentialCompetency(
                code="MED.BIO.CELL",
                label="Biologie cellulaire",
                keywords=("cellule", "membrane", "mitochondrie"),
                importance=3,
            ),
            ReferentialCompetency(
                code="MED.BIO.GEN",
                label="Génétique",
                keywords=("adn", "gène", "chromosome"),
                importance=3,
            ),
        ]
        rows = CorrectedCopyAlignmentService().process(
            text=document.extracted_text,
            referential=demo_referential,
            source_id=document.id,
        )
        questions = [
            QuestionAlignmentResponse(
                question_ref=row.question_ref,
                competency_code=row.competency_code,
                alignment_confidence=row.alignment_confidence,
                requires_confirmation=row.requires_confirmation,
                earned_points=(row.evidence.earned_points if row.evidence else None),
                max_points=(row.evidence.max_points if row.evidence else None),
            )
            for row in rows
        ]

    PostgresEducationDocumentRepository(get_database_url()).save(
        document,
        [
            StoredQuestionAlignment(
                question_ref=item.question_ref,
                competency_code=item.competency_code,
                alignment_confidence=item.alignment_confidence,
                requires_confirmation=item.requires_confirmation,
                earned_points=item.earned_points,
                max_points=item.max_points,
            )
            for item in questions
        ],
    )

    return AnalyzeDocumentResponse(
        document_id=document.id,
        source_hash=document.source_hash,
        kind=document.kind,
        provenance=document.provenance,
        questions=questions,
    )


class ConfirmAlignmentRequest(BaseModel):
    learner_id: UUID
    question_ref: str = Field(min_length=1, max_length=120)
    competency_code: str = Field(min_length=1, max_length=120)


@router.post("/documents/{document_id}/alignments/confirm", response_model=QuestionAlignmentResponse)
def confirm_document_alignment(
    document_id: UUID,
    payload: ConfirmAlignmentRequest,
    request: Request,
) -> QuestionAlignmentResponse:
    tenant_id = require_uuid_tenant(request)
    alignment = PostgresEducationDocumentRepository(get_database_url()).confirm_alignment(
        tenant_id=tenant_id,
        learner_id=payload.learner_id,
        document_id=document_id,
        question_ref=payload.question_ref,
        competency_code=payload.competency_code,
    )
    if alignment is None:
        raise HTTPException(status_code=404, detail="Document ou question introuvable.")
    return QuestionAlignmentResponse(
        question_ref=alignment.question_ref,
        competency_code=alignment.competency_code,
        alignment_confidence=alignment.alignment_confidence,
        requires_confirmation=False,
        earned_points=alignment.earned_points,
        max_points=alignment.max_points,
    )
