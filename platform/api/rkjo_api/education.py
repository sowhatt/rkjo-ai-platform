"""RKJO Education HTTP API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from rkjo_api.dependencies import get_education_course_service
from rkjo_api.education_dependencies import (
    get_education_learner_service,
    get_education_learning_service,
)
from rkjo_api.identity import get_authenticated_identity
from rkjo_education.course.models import Course
from rkjo_education.course.service import CourseService
from rkjo_education.learner.service import LearnerNotFoundError, LearnerService
from rkjo_education.learning.service import DuplicateEnrollmentError, LearningService

router = APIRouter(prefix="/education", tags=["education"])


class CourseCreateRequest(BaseModel):
    course_id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=300)
    subject: str = Field(min_length=1, max_length=200)
    level: str = Field(min_length=1, max_length=200)
    curriculum_id: str | None = None


class CourseResponse(BaseModel):
    course_id: str
    title: str
    subject: str
    level: str
    curriculum_id: str | None
    document_ids: list[str]


class AttachDocumentRequest(BaseModel):
    document_id: str = Field(min_length=1, max_length=300)


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


def require_tenant(request: Request) -> str:
    identity = get_authenticated_identity(request)
    if identity.tenant_id is None:
        raise HTTPException(
            status_code=400,
            detail="Authenticated identity must be bound to a tenant.",
        )
    return identity.tenant_id


def require_uuid_tenant(request: Request) -> UUID:
    tenant_id = require_tenant(request)
    try:
        return UUID(str(tenant_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Learner operations require a UUID tenant identifier.",
        ) from exc


def to_response(course: Course) -> CourseResponse:
    return CourseResponse(
        course_id=course.course_id,
        title=course.title,
        subject=course.subject,
        level=course.level,
        curriculum_id=course.curriculum_id,
        document_ids=list(course.document_ids),
    )


@router.post("/courses", response_model=CourseResponse, status_code=201)
def create_course(
    payload: CourseCreateRequest,
    request: Request,
    service: CourseService = Depends(get_education_course_service),
):
    tenant_id = require_tenant(request)
    try:
        course = service.create(
            Course(
                course_id=payload.course_id,
                tenant_id=tenant_id,
                title=payload.title,
                subject=payload.subject,
                level=payload.level,
                curriculum_id=payload.curriculum_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return to_response(course)


@router.get("/courses", response_model=list[CourseResponse])
def list_courses(
    request: Request,
    service: CourseService = Depends(get_education_course_service),
):
    return [
        to_response(course)
        for course in service.list_courses(tenant_id=require_tenant(request))
    ]


@router.get("/courses/{course_id}", response_model=CourseResponse)
def get_course(
    course_id: str,
    request: Request,
    service: CourseService = Depends(get_education_course_service),
):
    try:
        course = service.get(tenant_id=require_tenant(request), course_id=course_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Course not found.") from exc
    return to_response(course)


@router.post("/courses/{course_id}/documents", response_model=CourseResponse)
def attach_document(
    course_id: str,
    payload: AttachDocumentRequest,
    request: Request,
    service: CourseService = Depends(get_education_course_service),
):
    try:
        course = service.attach_document(
            tenant_id=require_tenant(request),
            course_id=course_id,
            document_id=payload.document_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Course not found.") from exc
    return to_response(course)


@router.post("/learners", response_model=LearnerResponse, status_code=201)
def create_learner(
    payload: CreateLearnerRequest,
    request: Request,
    service: LearnerService = Depends(get_education_learner_service),
) -> LearnerResponse:
    learner = service.create(
        tenant_id=require_uuid_tenant(request),
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
def get_learner(
    learner_id: UUID,
    request: Request,
    service: LearnerService = Depends(get_education_learner_service),
) -> LearnerResponse:
    try:
        learner = service.get(
            tenant_id=require_uuid_tenant(request),
            learner_id=learner_id,
        )
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
def enroll(
    payload: EnrollmentRequest,
    request: Request,
    service: LearningService = Depends(get_education_learning_service),
) -> EnrollmentResponse:
    try:
        enrollment = service.enroll(
            tenant_id=require_uuid_tenant(request),
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
def create_competency(
    payload: CompetencyRequest,
    request: Request,
    service: LearningService = Depends(get_education_learning_service),
) -> CompetencyResponse:
    competency = service.create_competency(
        tenant_id=require_uuid_tenant(request),
        code=payload.code,
        label=payload.label,
    )
    return CompetencyResponse(
        id=competency.id,
        code=competency.code,
        label=competency.label,
    )


@router.post("/progress", response_model=ProgressResponse)
def record_progress(
    payload: ProgressRequest,
    request: Request,
    service: LearningService = Depends(get_education_learning_service),
) -> ProgressResponse:
    try:
        progress = service.record_progress(
            tenant_id=require_uuid_tenant(request),
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
