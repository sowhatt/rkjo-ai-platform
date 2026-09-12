"""Asynchronous transcription API for RKJO Meeting Intelligence."""

from __future__ import annotations

import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from rkjo_api.dependencies import get_database_url, get_event_bus
from rkjo_api.meeting import get_meeting_repository, require_meeting, require_tenant
from rkjo_meeting_intelligence.application.transcription import (
    TranscriptionJob,
    TranscriptionStatus,
)
from rkjo_meeting_intelligence.infrastructure.postgres_repository import PostgresMeetingRepository
from rkjo_meeting_intelligence.infrastructure.transcription_repository import PostgresTranscriptionRepository


router = APIRouter(prefix="/meetings", tags=["meeting-intelligence-transcription"])
TRANSCRIPTION_QUEUE = "rkjo.meeting.transcription"


class TranscriptionCreateRequest(BaseModel):
    asset_id: str = Field(min_length=1)


class TranscriptionResponse(BaseModel):
    job_id: str
    asset_id: str
    status: str
    error: str | None


def get_transcription_repository() -> PostgresTranscriptionRepository:
    return PostgresTranscriptionRepository(get_database_url())


def get_transcription_bus():
    return get_event_bus()


def to_response(job: TranscriptionJob) -> TranscriptionResponse:
    return TranscriptionResponse(
        job_id=job.job_id,
        asset_id=job.asset_id,
        status=job.status.value,
        error=job.error,
    )


@router.post("/{meeting_id}/transcriptions", response_model=TranscriptionResponse, status_code=202)
def create_transcription(
    meeting_id: str,
    payload: TranscriptionCreateRequest,
    request: Request,
    meeting_repository: PostgresMeetingRepository = Depends(get_meeting_repository),
    repository: PostgresTranscriptionRepository = Depends(get_transcription_repository),
    bus=Depends(get_transcription_bus),
):
    tenant_id = require_tenant(request)
    require_meeting(meeting_repository, tenant_id=tenant_id, meeting_id=meeting_id)
    assets = meeting_repository.list_audio_assets(tenant_id=tenant_id, meeting_id=meeting_id)
    if not any(asset.asset_id == payload.asset_id for asset in assets):
        raise HTTPException(status_code=404, detail="Audio asset not found.")

    job = TranscriptionJob.queued(
        job_id=str(uuid4()),
        tenant_id=tenant_id,
        meeting_id=meeting_id,
        asset_id=payload.asset_id,
    )
    repository.save(job)
    try:
        bus.publish(
            TRANSCRIPTION_QUEUE,
            json.dumps(
                {
                    "job_id": job.job_id,
                    "tenant_id": job.tenant_id,
                    "meeting_id": job.meeting_id,
                    "asset_id": job.asset_id,
                }
            ),
        )
    except Exception as exc:
        failed = job.transition(TranscriptionStatus.FAILED, error=str(exc))
        repository.save(failed)
        raise HTTPException(status_code=503, detail="Transcription queue unavailable.") from exc
    finally:
        close = getattr(bus, "close", None)
        if close is not None:
            close()
    return to_response(job)


@router.get("/{meeting_id}/transcriptions/{job_id}", response_model=TranscriptionResponse)
def get_transcription(
    meeting_id: str,
    job_id: str,
    request: Request,
    meeting_repository: PostgresMeetingRepository = Depends(get_meeting_repository),
    repository: PostgresTranscriptionRepository = Depends(get_transcription_repository),
):
    tenant_id = require_tenant(request)
    require_meeting(meeting_repository, tenant_id=tenant_id, meeting_id=meeting_id)
    job = repository.get(tenant_id=tenant_id, meeting_id=meeting_id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Transcription job not found.")
    return to_response(job)
