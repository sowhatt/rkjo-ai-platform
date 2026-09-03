from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from rkjo_education.learner.repository import InMemoryLearnerRepository
from rkjo_education.learner.service import LearnerNotFoundError, LearnerService
from rkjo_education.learning.repository import InMemoryLearningRepository
from rkjo_education.learning.service import DuplicateEnrollmentError, LearningService


router = APIRouter(prefix="/education", tags=["education"])

_learner_service = LearnerService(InMemoryLearnerRepository())
_learning_service = LearningService(InMemoryLearningRepository())


def _tenant_id(request: Request) -> UUID:
    raw = getattr(request.state, "api_tenant_id", None)
    if raw is None:
        raise HTTPException(status_code=400, detail="Tenant binding is required.")
    try:
        return UUID(str(raw))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid tenant identifier.") from exc


class CreateLearnerRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    level: str = Field(min_length=1, max_length=120)


class LearnerResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    first_name: str
    last_name: str
    level: str
    status: str


class EnrollmentRequest(BaseModel):
    learner_id: UUID
    curriculum_id: UUID


class EnrollmentResponse(BaseModel):
    id: UUID
    learner_id: UUID
    curriculum_id: UUID
    status: str


class CompetencyRequest(BaseModel):
    code: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=255)


class CompetencyResponse(BaseModel):
    id: UUID
    code: str
    label: str


class ProgressRequest(BaseModel):
    learner_id: UUID
    course_id: UUID
    completion_percent: int = Field(ge=0, le=100)
    competency_scores: dict[str, int] = Field(default_factory=dict)


class ProgressResponse(BaseModel):
    id: UUID
    learner_id: UUID
    course_id: UUID
    completion_percent: int
    competency_scores: dict[str, int]


@router.post("/learners", response_model=LearnerResponse, status_code=201)
def create_learner(payload: CreateLearnerRequest, request: Request) -> LearnerResponse:
    learner = _learner_service.create(
        tenant_id=_tenant_id(request),
        first_name=payload.first_name,
        last_name=payload.last_name,
        level=payload.level,
    )
    return LearnerResponse(
        id=learner.id,
        tenant_id=learner.tenant_id,
        first_name=learner.first_name,
        last_name=learner.last_name,
        level=learner.level,
        status=learner.status.value,
    )


@router.get("/learners/{learner_id}", response_model=LearnerResponse)
def get_learner(learner_id: UUID, request: Request) -> LearnerResponse:
    try:
        learner = _learner_service.get(tenant_id=_tenant_id(request), learner_id=learner_id)
    except LearnerNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Learner not found.") from exc
    return LearnerResponse(
        id=learner.id,
        tenant_id=learner.tenant_id,
        first_name=learner.first_name,
        last_name=learner.last_name,
        level=learner.level,
        status=learner.status.value,
    )


@router.post("/enrollments", response_model=EnrollmentResponse, status_code=201)
def enroll(payload: EnrollmentRequest, request: Request) -> EnrollmentResponse:
    try:
        enrollment = _learning_service.enroll(
            tenant_id=_tenant_id(request),
            learner_id=payload.learner_id,
            curriculum_id=payload.curriculum_id,
        )
    except DuplicateEnrollmentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return EnrollmentResponse(
        id=enrollment.id,
        learner_id=enrollment.learner_id,
        curriculum_id=enrollment.curriculum_id,
        status=enrollment.status.value,
    )


@router.post("/competencies", response_model=CompetencyResponse, status_code=201)
def create_competency(payload: CompetencyRequest, request: Request) -> CompetencyResponse:
    competency = _learning_service.create_competency(
        tenant_id=_tenant_id(request),
        code=payload.code,
        label=payload.label,
    )
    return CompetencyResponse(id=competency.id, code=competency.code, label=competency.label)


@router.post("/progress", response_model=ProgressResponse)
def record_progress(payload: ProgressRequest, request: Request) -> ProgressResponse:
    try:
        progress = _learning_service.record_progress(
            tenant_id=_tenant_id(request),
            learner_id=payload.learner_id,
            course_id=payload.course_id,
            completion_percent=payload.completion_percent,
            competency_scores=payload.competency_scores,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ProgressResponse(
        id=progress.id,
        learner_id=progress.learner_id,
        course_id=progress.course_id,
        completion_percent=progress.completion_percent,
        competency_scores=progress.competency_scores,
    )
