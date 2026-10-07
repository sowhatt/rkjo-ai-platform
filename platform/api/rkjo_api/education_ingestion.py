"""Learner-first Education ingestion and referential alignment API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from rkjo_api.education import require_uuid_tenant
from rkjo_api.dependencies import get_database_url
from rkjo_api.education_dependencies import get_education_event_publisher
from rkjo_education.alignment import ReferentialCompetency
from rkjo_education.ingestion import DocumentKind, EducationIngestionService, Provenance
from rkjo_education.ingestion.extractor import DocumentExtractionError, EducationDocumentExtractor
from rkjo_education.ingestion.postgres_repository import PostgresEducationDocumentRepository, StoredQuestionAlignment
from rkjo_education.events import EducationEventType, EducationLearningEvent, EducationEventPublisher
from rkjo_education.intelligence.learner_model import LearnerModelProjector
from rkjo_education.intelligence.next_best_action import CompetencySignal, NBAContext, NextBestActionService
from rkjo_education.supervision.history import PostgresLearningEventHistory
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


class ApplyDocumentLearningRequest(BaseModel):
    learner_id: UUID


class AppliedEvidenceResponse(BaseModel):
    question_ref: str
    competency_code: str
    score: float
    weight: float
    alignment_confidence: float
    source: str = "corrected_copy"


class ApplyDocumentLearningResponse(BaseModel):
    document_id: UUID
    applied: bool
    evidence: list[AppliedEvidenceResponse]


@router.post("/documents/{document_id}/apply-learning", response_model=ApplyDocumentLearningResponse)
def apply_document_learning(
    document_id: UUID,
    payload: ApplyDocumentLearningRequest,
    request: Request,
    event_publisher: EducationEventPublisher = Depends(get_education_event_publisher),
) -> ApplyDocumentLearningResponse:
    tenant_id = require_uuid_tenant(request)
    repository = PostgresEducationDocumentRepository(get_database_url())
    alignments = repository.get_alignments(
        tenant_id=tenant_id,
        learner_id=payload.learner_id,
        document_id=document_id,
    )
    if alignments is None:
        raise HTTPException(status_code=404, detail="Document introuvable.")

    unresolved = [item for item in alignments if item.requires_confirmation]
    if unresolved:
        raise HTTPException(
            status_code=409,
            detail="Confirme les alignements incertains avant de les utiliser pour ton apprentissage.",
        )

    evidence = []
    for item in alignments:
        if (
            item.competency_code
            and item.earned_points is not None
            and item.max_points is not None
            and item.max_points > 0
        ):
            evidence.append(
                AppliedEvidenceResponse(
                    question_ref=item.question_ref,
                    competency_code=item.competency_code,
                    score=item.earned_points / item.max_points,
                    weight=0.8,
                    alignment_confidence=item.alignment_confidence,
                )
            )

    applied = repository.mark_learning_applied(
        tenant_id=tenant_id,
        learner_id=payload.learner_id,
        document_id=document_id,
    )
    if applied:
        history = PostgresLearningEventHistory(get_database_url())
        history.initialize_schema()
        for item in evidence:
            event = EducationLearningEvent(
                event_type=EducationEventType.CORRECTED_COPY_OBSERVED,
                tenant_id=tenant_id,
                learner_id=payload.learner_id,
                competency_code=item.competency_code,
                payload={
                    "document_id": str(document_id),
                    "question_ref": item.question_ref,
                    "alignment_confidence": item.alignment_confidence,
                    "score": item.score,
                    "weight": item.weight,
                    "source": item.source,
                    "affects_autonomy": False,
                },
            )
            # Persist synchronously for immediate learner-model/NBA consistency,
            # then publish for the distributed consumers.
            history.append(event)
            event_publisher.publish(event)
    return ApplyDocumentLearningResponse(
        document_id=document_id,
        applied=applied,
        evidence=evidence,
    )


class LearnerTodayRecommendationResponse(BaseModel):
    action: str
    target_competency: str | None
    rule_id: str
    explanation: str
    policy_version: str
    mastery: float | None = None
    autonomy: float | None = None
    retention: float | None = None
    challenge_id: UUID | None = None
    source: str = "computed"


@router.get("/learners/{learner_id}/today", response_model=LearnerTodayRecommendationResponse)
def get_learner_today_recommendation(
    learner_id: UUID,
    request: Request,
) -> LearnerTodayRecommendationResponse:
    tenant_id = require_uuid_tenant(request)
    history = PostgresLearningEventHistory(get_database_url())
    history.initialize_schema()
    events = history.list_for_learner(tenant_id=tenant_id, learner_id=learner_id)

    latest_decision = next(
        (event for event in reversed(events)
         if event.event_type == EducationEventType.NBA_DECIDED),
        None,
    )
    latest_observation = next(
        (event for event in reversed(events)
         if event.event_type != EducationEventType.NBA_DECIDED),
        None,
    )
    if (
        latest_decision is not None
        and latest_observation is not None
        and latest_decision.occurred_at >= latest_observation.occurred_at
    ):
        payload = latest_decision.payload
        code = latest_decision.competency_code
        state = (
            LearnerModelProjector().project(events, competency_code=code)
            if code else None
        )
        proof_request = next(
            (
                event for event in reversed(events)
                if event.event_type == EducationEventType.PROOF_REQUESTED
                and (code is None or event.competency_code == code)
            ),
            None,
        )
        raw_challenge_id = (
            proof_request.payload.get("proof_challenge_id")
            if proof_request is not None else None
        )
        challenge_id = None
        if raw_challenge_id:
            try:
                challenge_id = UUID(str(raw_challenge_id))
            except ValueError:
                challenge_id = None
        return LearnerTodayRecommendationResponse(
            action=str(payload.get("action") or "practice_similar"),
            target_competency=code,
            rule_id=str(payload.get("rule_id") or "R10"),
            explanation=str(payload.get("explanation") or "Continuer l’apprentissage."),
            policy_version=str(payload.get("policy_version") or "v2.3-policy-v1"),
            mastery=state.mastery if state else None,
            autonomy=state.autonomy if state else None,
            retention=state.retention if state else None,
            challenge_id=challenge_id,
            source="persisted_decision",
        )

    competency_codes = list(dict.fromkeys(
        event.competency_code for event in events if event.competency_code
    ))
    if not competency_codes:
        decision = NextBestActionService().decide_context(NBAContext())
        return LearnerTodayRecommendationResponse(
            action=decision.action.value,
            target_competency=decision.target_competency,
            rule_id=decision.rule_id,
            explanation=decision.explanation,
            policy_version=decision.policy_version,
        )

    projector = LearnerModelProjector()
    states = [
        projector.project(events, competency_code=code)
        for code in competency_codes
    ]
    signals = tuple(
        CompetencySignal(
            competency_code=state.competency_code,
            mastery=state.mastery,
            autonomy=state.autonomy,
            retention=state.retention,
            latest_correct=state.latest_correct,
            latest_observation_failed=state.latest_observation_failed,
            has_observation=state.has_observation,
            latest_help=state.latest_help,
            consecutive_failures=state.consecutive_failures,
            consecutive_no_hint_successes=state.consecutive_no_hint_successes,
            distinct_success_exercises=state.distinct_success_exercises,
            valid_proof=state.successful_proof,
            latest_proof=("passed" if state.successful_proof else None),
        )
        for state in states
    )
    target = min(states, key=lambda state: (state.mastery, state.retention))
    decision = NextBestActionService().decide_context(NBAContext(
        competencies=signals,
        target_competency=target.competency_code,
    ))
    target_state = next(
        (state for state in states if state.competency_code == decision.target_competency),
        target,
    )
    return LearnerTodayRecommendationResponse(
        action=decision.action.value,
        target_competency=decision.target_competency,
        rule_id=decision.rule_id,
        explanation=decision.explanation,
        policy_version=decision.policy_version,
        mastery=target_state.mastery,
        autonomy=target_state.autonomy,
        retention=target_state.retention,
    )
