from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from rkjo_api.education import require_uuid_tenant
from rkjo_api.education_dependencies import get_education_tutor_service
from rkjo_education.tutor.service import TutorService

router = APIRouter(prefix="/education", tags=["education"])


class TutorAskRequest(BaseModel):
    learner_id: UUID
    course_id: UUID
    question: str = Field(min_length=1, max_length=4000)


class TutorSourceResponse(BaseModel):
    citation: int
    document_id: str
    chunk_id: str
    score: float


class TutorAnswerResponse(BaseModel):
    learner_id: UUID
    course_id: UUID
    answer: str
    level: str
    completion_percent: int
    weak_competencies: list[str]
    sources: list[TutorSourceResponse]


@router.post("/tutor/ask", response_model=TutorAnswerResponse)
def ask_tutor(
    payload: TutorAskRequest,
    request: Request,
    service: TutorService = Depends(get_education_tutor_service),
) -> TutorAnswerResponse:
    try:
        result = service.ask(
            tenant_id=require_uuid_tenant(request),
            learner_id=payload.learner_id,
            course_id=payload.course_id,
            question=payload.question,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return TutorAnswerResponse(
        learner_id=result.learner_id,
        course_id=result.course_id,
        answer=result.answer,
        level=result.level,
        completion_percent=result.completion_percent,
        weak_competencies=result.weak_competencies,
        sources=[
            TutorSourceResponse(
                citation=source.citation,
                document_id=source.document_id,
                chunk_id=source.chunk_id,
                score=source.score,
            )
            for source in result.sources
        ],
    )
