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
)
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
