"""RKJO Meeting Intelligence HTTP API."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from rkjo_api.dependencies import get_database_url
from rkjo_api.identity import get_authenticated_identity
from rkjo_meeting_intelligence.application.create_meeting import CreateMeetingService
from rkjo_meeting_intelligence.application.meeting_service import MeetingService
from rkjo_meeting_intelligence.domain.models import (
    ActionItem,
    ActionStatus,
    Decision,
    DecisionStatus,
    Meeting,
    Participant,
    TranscriptSegment,
)
from rkjo_meeting_intelligence.infrastructure.postgres_repository import PostgresMeetingRepository


router = APIRouter(prefix="/meetings", tags=["meeting-intelligence"])


class MeetingCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    scheduled_at: datetime | None = None


class MeetingResponse(BaseModel):
    meeting_id: str
    title: str
    created_by: str
    scheduled_at: datetime | None
    started_at: datetime | None
    ended_at: datetime | None
    status: str


class ParticipantCreateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    role: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)


class ParticipantResponse(BaseModel):
    participant_id: str
    display_name: str
    role: str | None
    email: str | None


class TranscriptSegmentCreateRequest(BaseModel):
    text: str = Field(min_length=1)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    speaker_id: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class TranscriptSegmentResponse(BaseModel):
    segment_id: str
    text: str
    start_seconds: float
    end_seconds: float
    speaker_id: str | None
    confidence: float | None


class DecisionCreateRequest(BaseModel):
    text: str = Field(min_length=1)
    source_segment_id: str = Field(min_length=1)
    status: DecisionStatus = DecisionStatus.PROPOSED


class DecisionResponse(BaseModel):
    decision_id: str
    text: str
    source_segment_id: str
    status: str


class ActionCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    source_segment_id: str = Field(min_length=1)
    assignee_id: str | None = None
    due_at: datetime | None = None
    status: ActionStatus = ActionStatus.TODO


class ActionResponse(BaseModel):
    action_id: str
    title: str
    source_segment_id: str
    assignee_id: str | None
    due_at: datetime | None
    status: str


def get_meeting_repository() -> PostgresMeetingRepository:
    return PostgresMeetingRepository(get_database_url())


def get_meeting_create_service(
    repository: PostgresMeetingRepository = Depends(get_meeting_repository),
) -> CreateMeetingService:
    return CreateMeetingService(repository=repository)


def require_tenant(request: Request) -> str:
    identity = get_authenticated_identity(request)
    if identity.tenant_id is None:
        raise HTTPException(
            status_code=400,
            detail="Authenticated identity must be bound to a tenant.",
        )
    return identity.tenant_id


def resolve_creator(request: Request) -> str:
    identity = get_authenticated_identity(request)
    return identity.subject or "api-user"


def require_meeting(
    repository: PostgresMeetingRepository,
    *,
    tenant_id: str,
    meeting_id: str,
) -> Meeting:
    meeting = repository.get(tenant_id=tenant_id, meeting_id=meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found.")
    return meeting


def to_response(meeting: Meeting) -> MeetingResponse:
    return MeetingResponse(
        meeting_id=meeting.meeting_id,
        title=meeting.title,
        created_by=meeting.created_by,
        scheduled_at=meeting.scheduled_at,
        started_at=meeting.started_at,
        ended_at=meeting.ended_at,
        status=meeting.status.value,
    )


@router.post("", response_model=MeetingResponse, status_code=201)
def create_meeting(
    payload: MeetingCreateRequest,
    request: Request,
    service: CreateMeetingService = Depends(get_meeting_create_service),
):
    meeting = service.create(
        tenant_id=require_tenant(request),
        title=payload.title,
        created_by=resolve_creator(request),
        scheduled_at=payload.scheduled_at,
    )
    return to_response(meeting)


@router.get("", response_model=list[MeetingResponse])
def list_meetings(
    request: Request,
    repository: PostgresMeetingRepository = Depends(get_meeting_repository),
):
    return [
        to_response(meeting)
        for meeting in repository.list_for_tenant(tenant_id=require_tenant(request))
    ]


@router.get("/{meeting_id}", response_model=MeetingResponse)
def get_meeting(
    meeting_id: str,
    request: Request,
    repository: PostgresMeetingRepository = Depends(get_meeting_repository),
):
    return to_response(
        require_meeting(
            repository,
            tenant_id=require_tenant(request),
            meeting_id=meeting_id,
        )
    )


def _transition(
    meeting_id: str,
    request: Request,
    repository: PostgresMeetingRepository,
    method_name: str,
) -> MeetingResponse:
    tenant_id = require_tenant(request)
    meeting = require_meeting(repository, tenant_id=tenant_id, meeting_id=meeting_id)
    service = MeetingService()
    updated = getattr(service, method_name)(meeting)
    repository.save(updated)
    return to_response(updated)


@router.post("/{meeting_id}/start", response_model=MeetingResponse)
def start_meeting(meeting_id: str, request: Request, repository: PostgresMeetingRepository = Depends(get_meeting_repository)):
    return _transition(meeting_id, request, repository, "start_recording")


@router.post("/{meeting_id}/stop", response_model=MeetingResponse)
def stop_meeting(meeting_id: str, request: Request, repository: PostgresMeetingRepository = Depends(get_meeting_repository)):
    return _transition(meeting_id, request, repository, "stop_recording")


@router.post("/{meeting_id}/review", response_model=MeetingResponse)
def mark_review(meeting_id: str, request: Request, repository: PostgresMeetingRepository = Depends(get_meeting_repository)):
    return _transition(meeting_id, request, repository, "mark_ready_for_review")


@router.post("/{meeting_id}/validate", response_model=MeetingResponse)
def validate_meeting(meeting_id: str, request: Request, repository: PostgresMeetingRepository = Depends(get_meeting_repository)):
    return _transition(meeting_id, request, repository, "validate")


@router.post("/{meeting_id}/archive", response_model=MeetingResponse)
def archive_meeting(meeting_id: str, request: Request, repository: PostgresMeetingRepository = Depends(get_meeting_repository)):
    return _transition(meeting_id, request, repository, "archive")


@router.post("/{meeting_id}/participants", response_model=ParticipantResponse, status_code=201)
def add_participant(
    meeting_id: str,
    payload: ParticipantCreateRequest,
    request: Request,
    repository: PostgresMeetingRepository = Depends(get_meeting_repository),
):
    tenant_id = require_tenant(request)
    require_meeting(repository, tenant_id=tenant_id, meeting_id=meeting_id)
    participant = Participant(
        participant_id=str(uuid4()),
        meeting_id=meeting_id,
        tenant_id=tenant_id,
        display_name=payload.display_name,
        role=payload.role,
        email=payload.email,
    )
    repository.save_participant(participant)
    return ParticipantResponse(
        participant_id=participant.participant_id,
        display_name=participant.display_name,
        role=participant.role,
        email=participant.email,
    )


@router.get("/{meeting_id}/participants", response_model=list[ParticipantResponse])
def list_participants(meeting_id: str, request: Request, repository: PostgresMeetingRepository = Depends(get_meeting_repository)):
    tenant_id = require_tenant(request)
    require_meeting(repository, tenant_id=tenant_id, meeting_id=meeting_id)
    return [
        ParticipantResponse(
            participant_id=item.participant_id,
            display_name=item.display_name,
            role=item.role,
            email=item.email,
        )
        for item in repository.list_participants(tenant_id=tenant_id, meeting_id=meeting_id)
    ]


@router.post("/{meeting_id}/transcript", response_model=TranscriptSegmentResponse, status_code=201)
def add_transcript_segment(
    meeting_id: str,
    payload: TranscriptSegmentCreateRequest,
    request: Request,
    repository: PostgresMeetingRepository = Depends(get_meeting_repository),
):
    tenant_id = require_tenant(request)
    require_meeting(repository, tenant_id=tenant_id, meeting_id=meeting_id)
    segment = TranscriptSegment(
        segment_id=str(uuid4()),
        meeting_id=meeting_id,
        tenant_id=tenant_id,
        text=payload.text,
        start_seconds=payload.start_seconds,
        end_seconds=payload.end_seconds,
        speaker_id=payload.speaker_id,
        confidence=payload.confidence,
    )
    repository.save_transcript_segment(segment)
    return TranscriptSegmentResponse(
        segment_id=segment.segment_id,
        text=segment.text,
        start_seconds=segment.start_seconds,
        end_seconds=segment.end_seconds,
        speaker_id=segment.speaker_id,
        confidence=segment.confidence,
    )


@router.get("/{meeting_id}/transcript", response_model=list[TranscriptSegmentResponse])
def list_transcript(meeting_id: str, request: Request, repository: PostgresMeetingRepository = Depends(get_meeting_repository)):
    tenant_id = require_tenant(request)
    require_meeting(repository, tenant_id=tenant_id, meeting_id=meeting_id)
    return [
        TranscriptSegmentResponse(
            segment_id=item.segment_id,
            text=item.text,
            start_seconds=item.start_seconds,
            end_seconds=item.end_seconds,
            speaker_id=item.speaker_id,
            confidence=item.confidence,
        )
        for item in repository.list_transcript_segments(tenant_id=tenant_id, meeting_id=meeting_id)
    ]


@router.post("/{meeting_id}/decisions", response_model=DecisionResponse, status_code=201)
def add_decision(
    meeting_id: str,
    payload: DecisionCreateRequest,
    request: Request,
    repository: PostgresMeetingRepository = Depends(get_meeting_repository),
):
    tenant_id = require_tenant(request)
    require_meeting(repository, tenant_id=tenant_id, meeting_id=meeting_id)
    decision = Decision(
        decision_id=str(uuid4()),
        meeting_id=meeting_id,
        tenant_id=tenant_id,
        text=payload.text,
        source_segment_id=payload.source_segment_id,
        status=payload.status,
    )
    repository.save_decision(decision)
    return DecisionResponse(
        decision_id=decision.decision_id,
        text=decision.text,
        source_segment_id=decision.source_segment_id,
        status=decision.status.value,
    )


@router.get("/{meeting_id}/decisions", response_model=list[DecisionResponse])
def list_decisions(meeting_id: str, request: Request, repository: PostgresMeetingRepository = Depends(get_meeting_repository)):
    tenant_id = require_tenant(request)
    require_meeting(repository, tenant_id=tenant_id, meeting_id=meeting_id)
    return [
        DecisionResponse(
            decision_id=item.decision_id,
            text=item.text,
            source_segment_id=item.source_segment_id,
            status=item.status.value,
        )
        for item in repository.list_decisions(tenant_id=tenant_id, meeting_id=meeting_id)
    ]


@router.post("/{meeting_id}/actions", response_model=ActionResponse, status_code=201)
def add_action(
    meeting_id: str,
    payload: ActionCreateRequest,
    request: Request,
    repository: PostgresMeetingRepository = Depends(get_meeting_repository),
):
    tenant_id = require_tenant(request)
    require_meeting(repository, tenant_id=tenant_id, meeting_id=meeting_id)
    action = ActionItem(
        action_id=str(uuid4()),
        meeting_id=meeting_id,
        tenant_id=tenant_id,
        title=payload.title,
        source_segment_id=payload.source_segment_id,
        assignee_id=payload.assignee_id,
        due_at=payload.due_at,
        status=payload.status,
    )
    repository.save_action(action)
    return ActionResponse(
        action_id=action.action_id,
        title=action.title,
        source_segment_id=action.source_segment_id,
        assignee_id=action.assignee_id,
        due_at=action.due_at,
        status=action.status.value,
    )


@router.get("/{meeting_id}/actions", response_model=list[ActionResponse])
def list_actions(meeting_id: str, request: Request, repository: PostgresMeetingRepository = Depends(get_meeting_repository)):
    tenant_id = require_tenant(request)
    require_meeting(repository, tenant_id=tenant_id, meeting_id=meeting_id)
    return [
        ActionResponse(
            action_id=item.action_id,
            title=item.title,
            source_segment_id=item.source_segment_id,
            assignee_id=item.assignee_id,
            due_at=item.due_at,
            status=item.status.value,
        )
        for item in repository.list_actions(tenant_id=tenant_id, meeting_id=meeting_id)
    ]
