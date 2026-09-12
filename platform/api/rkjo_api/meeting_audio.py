"""Audio ingestion API for RKJO Meeting Intelligence."""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from rkjo_api.meeting import get_meeting_repository, require_meeting, require_tenant
from rkjo_meeting_intelligence.domain.models import AudioAsset
from rkjo_meeting_intelligence.infrastructure.audio_storage import LocalAudioStorage
from rkjo_meeting_intelligence.infrastructure.postgres_repository import PostgresMeetingRepository


router = APIRouter(prefix="/meetings", tags=["meeting-intelligence-audio"])

MAX_AUDIO_BYTES = 250 * 1024 * 1024
ALLOWED_MEDIA_PREFIXES = ("audio/", "video/")


class AudioAssetResponse(BaseModel):
    asset_id: str
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    storage_key: str
    created_at: datetime


def get_audio_storage() -> LocalAudioStorage:
    root = os.getenv("RKJO_MEETING_AUDIO_ROOT", "/tmp/rkjo-meeting-audio")
    return LocalAudioStorage(root)


def to_audio_response(asset: AudioAsset) -> AudioAssetResponse:
    return AudioAssetResponse(
        asset_id=asset.asset_id,
        original_filename=asset.original_filename,
        content_type=asset.content_type,
        size_bytes=asset.size_bytes,
        sha256=asset.sha256,
        storage_key=asset.storage_key,
        created_at=asset.created_at,
    )


@router.post("/{meeting_id}/audio", response_model=AudioAssetResponse, status_code=201)
async def upload_audio(
    meeting_id: str,
    request: Request,
    file: UploadFile = File(...),
    repository: PostgresMeetingRepository = Depends(get_meeting_repository),
    storage: LocalAudioStorage = Depends(get_audio_storage),
):
    tenant_id = require_tenant(request)
    require_meeting(repository, tenant_id=tenant_id, meeting_id=meeting_id)

    filename = Path(file.filename or "").name
    if not filename:
        raise HTTPException(status_code=422, detail="Audio filename is required.")

    content_type = (file.content_type or "application/octet-stream").lower()
    if not content_type.startswith(ALLOWED_MEDIA_PREFIXES):
        raise HTTPException(
            status_code=415,
            detail="Only audio or video media can be uploaded.",
        )

    content = await file.read(MAX_AUDIO_BYTES + 1)
    if not content:
        raise HTTPException(status_code=422, detail="Audio file must not be empty.")
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Audio file exceeds the 250 MiB upload limit.",
        )

    asset_id = str(uuid4())
    sha256 = hashlib.sha256(content).hexdigest()
    storage_key = storage.save(
        tenant_id=tenant_id,
        meeting_id=meeting_id,
        asset_id=asset_id,
        filename=filename,
        content=content,
    )
    asset = AudioAsset(
        asset_id=asset_id,
        meeting_id=meeting_id,
        tenant_id=tenant_id,
        original_filename=filename,
        content_type=content_type,
        size_bytes=len(content),
        sha256=sha256,
        storage_key=storage_key,
        created_at=datetime.now(UTC),
    )
    repository.save_audio_asset(asset)
    return to_audio_response(asset)


@router.get("/{meeting_id}/audio", response_model=list[AudioAssetResponse])
def list_audio_assets(
    meeting_id: str,
    request: Request,
    repository: PostgresMeetingRepository = Depends(get_meeting_repository),
):
    tenant_id = require_tenant(request)
    require_meeting(repository, tenant_id=tenant_id, meeting_id=meeting_id)
    return [
        to_audio_response(asset)
        for asset in repository.list_audio_assets(
            tenant_id=tenant_id,
            meeting_id=meeting_id,
        )
    ]
