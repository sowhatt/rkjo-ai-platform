"""Opt-in local-only pilot: durably stage WAV and return own metadata.

Never enables paid processing or ASR. Avoid real students' sensitive recordings:
database BYTEA storage has no application-layer encryption.
"""
from __future__ import annotations

import os
from ipaddress import ip_address
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from psycopg import Error as PostgresError

from rkjo_education.curriculum.study_audio_probe import StudyAudioError, probe_study_wav
from rkjo_education.curriculum.study_audio_postgres import (
    PostgresStudyAudioStaging, StagedAudioNotFound,
)
from rkjo_education.curriculum.study_media_intake import AUDIO_MAX_BYTES, SourceKind, SourceLanguage, StudyMediaRequest

router = APIRouter(prefix="/education/study", tags=["education-study-audio"])


def _identity_and_gate(request: Request) -> tuple[str, str]:
    client = request.client.host if request.client else None
    try:
        local = client is not None and ip_address(client).is_loopback
    except ValueError:
        local = False
    if (os.getenv("RKJO_EDUCATION_AUDIO_STAGING") != "enabled"
            or os.getenv("RKJO_AUDIO_STORAGE_ACK") != "local-postgres-only"
            or not local):
        raise HTTPException(status_code=404, detail="Local audio staging disabled")
    tenant = getattr(request.state, "api_tenant_id", None)
    student = getattr(request.state, "api_subject", None)
    if not tenant or not student or not request.headers.get("authorization", "").startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Individual tenant-bound Bearer required")
    return str(tenant), str(student)


def _store() -> PostgresStudyAudioStaging:
    database_url = os.getenv("RKJO_EDUCATION_AUDIO_DATABASE_URL", "").strip()
    if not database_url:
        raise HTTPException(status_code=503, detail="Dedicated audio staging database not configured")
    return PostgresStudyAudioStaging(database_url)


@router.post("/stage-audio", status_code=201)
async def stage_audio(
    request: Request, file: UploadFile = File(...),
    programme_id: str = Form(..., min_length=1, max_length=120),
    ue_id: str = Form(..., min_length=1, max_length=120),
    recording_authorized: bool = Form(False),
    processing_rights_confirmed: bool = Form(False),
) -> dict[str, object]:
    tenant, learner = _identity_and_gate(request)
    if not recording_authorized or not processing_rights_confirmed:
        raise HTTPException(status_code=422, detail="Audio permissions must be confirmed")
    if file.content_type not in ("audio/wav", "audio/x-wav", "audio/wave"):
        raise HTTPException(status_code=415, detail="WAV required for this pilot")
    try:
        data = await file.read(AUDIO_MAX_BYTES + 1)
        if len(data) > AUDIO_MAX_BYTES:
            raise HTTPException(status_code=413, detail="Audio exceeds 50 MiB")
        probe = probe_study_wav(data)
        StudyMediaRequest(
            tenant_id=tenant, learner_id=learner, ue_id=ue_id,
            kind=SourceKind.LECTURE_AUDIO,
            filename=file.filename or "course.wav", size_bytes=len(data),
            content_type="audio/wav", language=SourceLanguage.UNKNOWN,
            recording_consent_confirmed=True, rights_confirmed=True,
        )
        store = _store()
        store.initialize_schema()
        return store.stage(
            tenant_id=tenant, learner_id=learner, programme_id=programme_id,
            ue_id=ue_id, filename=(file.filename or "course.wav")[:255],
            data=data, probe=probe,
        )
    except (StudyAudioError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PostgresError as exc:
        raise HTTPException(status_code=503, detail="Audio staging database unavailable") from exc
    finally:
        await file.close()


@router.get("/staged-audio/{source_id}")
def get_staged_audio(request: Request, source_id: UUID) -> dict[str, object]:
    tenant, learner = _identity_and_gate(request)
    try:
        return _store().get(tenant_id=tenant, learner_id=learner, source_id=str(source_id))
    except StagedAudioNotFound as exc:
        raise HTTPException(status_code=404, detail="Audio not found") from exc
    except PostgresError as exc:
        raise HTTPException(status_code=503, detail="Audio staging database unavailable") from exc


@router.delete("/staged-audio/{source_id}")
def delete_staged_audio(request: Request, source_id: UUID) -> dict[str, bool]:
    tenant, learner = _identity_and_gate(request)
    try:
        if not _store().delete(tenant_id=tenant, learner_id=learner, source_id=str(source_id)):
            raise HTTPException(status_code=404, detail="Audio not found")
        return {"deleted": True}
    except PostgresError as exc:
        raise HTTPException(status_code=503, detail="Audio staging database unavailable") from exc
