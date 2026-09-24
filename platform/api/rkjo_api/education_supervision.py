"""Education supervision HTTP API."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from rkjo_api.education import require_uuid_tenant
from rkjo_education.supervision import (
    LearnerSupervisionProjection,
    LearnerSupervisionState,
)

router = APIRouter(
    prefix="/education/supervision",
    tags=["education-supervision"],
)

_projection = LearnerSupervisionProjection()


def get_supervision_projection() -> LearnerSupervisionProjection:
    return _projection


@router.get(
    "/learners/{learner_id}/snapshot",
    response_model=LearnerSupervisionState,
)
def get_learner_snapshot(
    learner_id: UUID,
    request: Request,
    projection: LearnerSupervisionProjection = Depends(get_supervision_projection),
) -> LearnerSupervisionState:
    state = projection.get(
        tenant_id=require_uuid_tenant(request),
        learner_id=learner_id,
    )
    if state is None:
        raise HTTPException(
            status_code=404,
            detail="Learner supervision state not found.",
        )
    return state


@router.get(
    "/snapshot",
    response_model=list[LearnerSupervisionState],
)
def get_tenant_snapshot(
    request: Request,
    projection: LearnerSupervisionProjection = Depends(get_supervision_projection),
) -> list[LearnerSupervisionState]:
    return projection.list_for_tenant(
        tenant_id=require_uuid_tenant(request)
    )
