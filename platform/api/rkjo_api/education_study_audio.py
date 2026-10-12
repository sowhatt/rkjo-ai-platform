"""Authenticated, stateless audio WAV admission pilot (no storage or ASR)."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from rkjo_education.curriculum.study_audio_probe import StudyAudioError, probe_study_wav
from rkjo_education.curriculum.study_media_intake import (
    AUDIO_MAX_BYTES, SourceKind, SourceLanguage, StudyMediaRequest,
)

router = APIRouter(prefix="/education/study", tags=["education-study-audio"])


@router.post("/inspect-audio")
async def inspect_study_audio(
    request: Request,
    file: UploadFile = File(...),
    programme_id: str = Form(..., min_length=1, max_length=120),
    ue_id: str = Form(..., min_length=1, max_length=120),
    recording_authorized: bool = Form(False),
    processing_rights_confirmed: bool = Form(False),
) -> dict[str, object]:
    tenant = getattr(request.state, "api_tenant_id", None)
    student = getattr(request.state, "api_subject", None)
    if not tenant or not student or not request.headers.get("authorization", "").startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Individual tenant-bound Bearer identity required")
    if not recording_authorized or not processing_rights_confirmed:
        raise HTTPException(status_code=422, detail="Recording permission and processing rights must be confirmed")
    if file.content_type not in {"audio/wav", "audio/x-wav", "audio/wave"}:
        raise HTTPException(status_code=415, detail="Pilot currently accepts WAV files only")
    try:
        blob = await file.read(AUDIO_MAX_BYTES + 1)
        if len(blob) > AUDIO_MAX_BYTES:
            raise HTTPException(status_code=413, detail="Audio exceeds 50 MiB")
        probe = probe_study_wav(blob)
        StudyMediaRequest(
            tenant_id=str(tenant), learner_id=str(student), ue_id=ue_id,
            kind=SourceKind.LECTURE_AUDIO,
            filename=file.filename or "course.wav", size_bytes=probe.size_bytes,
            content_type="audio/wav", language=SourceLanguage.UNKNOWN,
            rights_confirmed=True, recording_consent_confirmed=True,
        )
    except StudyAudioError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()

    return {
        "programme_id": programme_id,
        "ue_id": ue_id,
        "filename": file.filename,
        "sha256": probe.sha256,
        "size_bytes": probe.size_bytes,
        "duration_ms": probe.duration_ms,
        "sample_rate": probe.sample_rate,
        "channels": probe.channels,
        "encoding": probe.encoding,
        "inspection_only": True,
        "stored": False,
        "transcription_started": False,
        "payment_started": False,
    }
