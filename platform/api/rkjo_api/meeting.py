"""RKJO Meeting Intelligence HTTP API."""

from __future__ import annotations

from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from pydantic import BaseModel, Field

from rkjo_api.dependencies import (
    get_meeting_create_service,
    get_meeting_repository,
)
from rkjo_api.identity import (
    get_authenticated_identity,
)
from rkjo_meeting_intelligence.application.create_meeting import (
    CreateMeetingService,
)
from rkjo_meeting_intelligence.domain.models import (
    Meeting,
)
from rkjo_meeting_intelligence.infrastructure.memory_repository import (
    InMemoryMeetingRepository,
)


router = APIRouter(
    prefix="/meetings",
    tags=["meeting-intelligence"],
)


class MeetingCreateRequest(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=300,
    )
    scheduled_at: datetime | None = None


class MeetingResponse(BaseModel):
    meeting_id: str
    title: str
    created_by: str
    scheduled_at: datetime | None
    status: str


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


def resolve_creator(
    request: Request,
) -> str:
    identity = get_authenticated_identity(
        request
    )

    if identity.subject:
        return identity.subject

    return "api-user"


def to_response(
    meeting: Meeting,
) -> MeetingResponse:
    return MeetingResponse(
        meeting_id=meeting.meeting_id,
        title=meeting.title,
        created_by=meeting.created_by,
        scheduled_at=meeting.scheduled_at,
        status=meeting.status.value,
    )


@router.post(
    "",
    response_model=MeetingResponse,
    status_code=201,
)
def create_meeting(
    payload: MeetingCreateRequest,
    request: Request,
    service: CreateMeetingService = Depends(
        get_meeting_create_service
    ),
):
    tenant_id = require_tenant(
        request
    )

    meeting = service.create(
        tenant_id=tenant_id,
        title=payload.title,
        created_by=resolve_creator(
            request
        ),
        scheduled_at=payload.scheduled_at,
    )

    return to_response(
        meeting
    )


@router.get(
    "",
    response_model=list[MeetingResponse],
)
def list_meetings(
    request: Request,
    repository: InMemoryMeetingRepository = Depends(
        get_meeting_repository
    ),
):
    tenant_id = require_tenant(
        request
    )

    meetings = repository.list_for_tenant(
        tenant_id=tenant_id
    )

    return [
        to_response(meeting)
        for meeting in meetings
    ]


@router.get(
    "/{meeting_id}",
    response_model=MeetingResponse,
)
def get_meeting(
    meeting_id: str,
    request: Request,
    repository: InMemoryMeetingRepository = Depends(
        get_meeting_repository
    ),
):
    tenant_id = require_tenant(
        request
    )

    meeting = repository.get(
        tenant_id=tenant_id,
        meeting_id=meeting_id,
    )

    if meeting is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found.",
        )

    return to_response(
        meeting
    )
