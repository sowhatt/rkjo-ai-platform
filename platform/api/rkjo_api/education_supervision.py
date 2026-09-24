"""Education supervision HTTP API."""

import asyncio
import json
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


async def supervision_event_stream(
    *,
    request: Request,
    tenant_id: UUID,
    projection: LearnerSupervisionProjection,
    poll_interval_seconds: float = 0.25,
):
    """Stream tenant-scoped supervision snapshots when their state changes."""
    last_version: tuple[tuple[str, str], ...] | None = None

    while not await request.is_disconnected():
        states = projection.list_for_tenant(tenant_id=tenant_id)
        version = tuple(
            (str(state.learner_id), str(state.last_event_id))
            for state in states
        )

        if version != last_version:
            payload = [
                state.model_dump(mode="json")
                for state in states
            ]
            yield "event: supervision.snapshot\n"
            yield f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"
            last_version = version

        await asyncio.sleep(poll_interval_seconds)


@router.get("/stream")
def stream_tenant_supervision(
    request: Request,
    projection: LearnerSupervisionProjection = Depends(get_supervision_projection),
):
    tenant_id = require_uuid_tenant(request)
    return StreamingResponse(
        supervision_event_stream(
            request=request,
            tenant_id=tenant_id,
            projection=projection,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
