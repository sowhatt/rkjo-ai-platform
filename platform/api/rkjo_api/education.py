"""RKJO Education HTTP API."""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from pydantic import BaseModel, Field

from rkjo_api.dependencies import (
    get_education_course_service,
    get_rag_answering_service,
)
from rkjo_api.security import ApiRole, role_allows
from rkjo_kernel.rag.rag_answering import RAGAnsweringService
from rkjo_kernel.rag.retrieval_filters import RetrievalFilters
from rkjo_api.identity import (
    get_authenticated_identity,
)
from rkjo_education.course.models import (
    Course,
)
from rkjo_education.course.service import (
    CourseService,
)


router = APIRouter(
    prefix="/education",
    tags=["education"],
)


class CourseCreateRequest(BaseModel):
    course_id: str = Field(
        min_length=1,
        max_length=200,
    )
    title: str = Field(
        min_length=1,
        max_length=300,
    )
    subject: str = Field(
        min_length=1,
        max_length=200,
    )
    level: str = Field(
        min_length=1,
        max_length=200,
    )
    curriculum_id: str | None = None


class CourseResponse(BaseModel):
    course_id: str
    title: str
    subject: str
    level: str
    curriculum_id: str | None
    document_ids: list[str]


class AttachDocumentRequest(BaseModel):
    document_id: str = Field(
        min_length=1,
        max_length=300,
    )


def require_tenant(
    request: Request,
) -> str:
    identity = get_authenticated_identity(
        request
    )

    if identity.tenant_id is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Authenticated identity "
                "must be bound to a tenant."
            ),
        )

    return identity.tenant_id


def to_response(
    course: Course,
) -> CourseResponse:
    return CourseResponse(
        course_id=course.course_id,
        title=course.title,
        subject=course.subject,
        level=course.level,
        curriculum_id=(
            course.curriculum_id
        ),
        document_ids=list(
            course.document_ids
        ),
    )


@router.post(
    "/courses",
    response_model=CourseResponse,
    status_code=201,
)
def create_course(
    payload: CourseCreateRequest,
    request: Request,
    service: CourseService = Depends(
        get_education_course_service
    ),
):
    tenant_id = require_tenant(
        request
    )

    try:
        course = service.create(
            Course(
                course_id=payload.course_id,
                tenant_id=tenant_id,
                title=payload.title,
                subject=payload.subject,
                level=payload.level,
                curriculum_id=(
                    payload.curriculum_id
                ),
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return to_response(
        course
    )


@router.get(
    "/courses",
    response_model=list[CourseResponse],
)
def list_courses(
    request: Request,
    service: CourseService = Depends(
        get_education_course_service
    ),
):
    tenant_id = require_tenant(
        request
    )

    courses = service.list_courses(
        tenant_id=tenant_id
    )

    return [
        to_response(course)
        for course in courses
    ]


@router.get(
    "/courses/{course_id}",
    response_model=CourseResponse,
)
def get_course(
    course_id: str,
    request: Request,
    service: CourseService = Depends(
        get_education_course_service
    ),
):
    tenant_id = require_tenant(
        request
    )

    try:
        course = service.get(
            tenant_id=tenant_id,
            course_id=course_id,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail="Course not found.",
        ) from exc

    return to_response(
        course
    )


@router.post(
    "/courses/{course_id}/documents",
    response_model=CourseResponse,
)
def attach_document(
    course_id: str,
    payload: AttachDocumentRequest,
    request: Request,
    service: CourseService = Depends(
        get_education_course_service
    ),
):
    tenant_id = require_tenant(
        request
    )

    try:
        course = service.attach_document(
            tenant_id=tenant_id,
            course_id=course_id,
            document_id=(
                payload.document_id
            ),
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail="Course not found.",
        ) from exc

    return to_response(
        course
    )


class CourseQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    document_id: str = Field(min_length=1, max_length=300)
    limit: int = Field(default=5, ge=1, le=20)


class CourseAnswerSource(BaseModel):
    citation: int
    document_id: str
    chunk_id: str
    score: float
    page_number: int | None = None


class CourseAnswerResponse(BaseModel):
    course_id: str
    document_id: str
    answer: str
    sanitized_query: str
    sources: list[CourseAnswerSource]


@router.post(
    "/courses/{course_id}/answer",
    response_model=CourseAnswerResponse,
)
def answer_course_document(
    course_id: str,
    payload: CourseQuestionRequest,
    request: Request,
    courses: CourseService = Depends(get_education_course_service),
    answering: RAGAnsweringService = Depends(get_rag_answering_service),
) -> CourseAnswerResponse:
    """Answer using only one document explicitly attached to an authorized course.

    Until enrollment-based learner access exists, this route is operator-only.
    """
    identity = get_authenticated_identity(request)
    if not role_allows(actual_role=identity.role, required_role=ApiRole.OPERATOR):
        raise HTTPException(status_code=403, detail="Course access requires operator role.")
    tenant_id = identity.tenant_id
    if not tenant_id or not tenant_id.strip():
        raise HTTPException(status_code=403, detail="Tenant-bound identity required.")
    try:
        course = courses.get(tenant_id=tenant_id, course_id=course_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Course not found.") from None
    if payload.document_id not in course.document_ids:
        raise HTTPException(status_code=404, detail="Document not found in course.")
    result = answering.answer(
        payload.question,
        limit=payload.limit,
        filters=RetrievalFilters(metadata={
            "tenant_id": tenant_id,
            "evidence_document_id": payload.document_id,
        }),
    )
    # Fail closed even for a misconfigured retrieval or answering adapter.
    if any(source.document_id != payload.document_id for source in result.sources):
        raise HTTPException(status_code=502, detail="Unscoped source returned by RAG.")
    return CourseAnswerResponse(
        course_id=course_id,
        document_id=payload.document_id,
        answer=result.answer,
        sanitized_query=result.sanitized_query,
        sources=[CourseAnswerSource(
            citation=source.citation, document_id=source.document_id,
            chunk_id=source.chunk_id, score=source.score,
            page_number=source.page_number,
        ) for source in result.sources],
    )
