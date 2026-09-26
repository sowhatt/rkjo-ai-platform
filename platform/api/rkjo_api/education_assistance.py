from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from rkjo_api.education import require_uuid_tenant
from rkjo_api.education_dependencies import get_education_event_publisher
from rkjo_education.events import EducationEventPublisher, EducationEventType, EducationLearningEvent


router = APIRouter(prefix="/education", tags=["education"])


class HintRequest(BaseModel):
    learner_id: UUID
    course_id: UUID | None = None
    assessment_id: UUID | None = None
    question_id: UUID | None = None
    competency_code: str | None = None


class HintResponse(BaseModel):
    recorded: bool = True


@router.post("/hints", response_model=HintResponse)
def request_hint(
    payload: HintRequest,
    request: Request,
    event_publisher: EducationEventPublisher = Depends(get_education_event_publisher),
) -> HintResponse:
    tenant_id = require_uuid_tenant(request)
    event_publisher.publish(
        EducationLearningEvent(
            event_type=EducationEventType.HINT_REQUESTED,
            tenant_id=tenant_id,
            learner_id=payload.learner_id,
            course_id=payload.course_id,
            assessment_id=payload.assessment_id,
            question_id=payload.question_id,
            competency_code=payload.competency_code,
        )
    )
    return HintResponse()
