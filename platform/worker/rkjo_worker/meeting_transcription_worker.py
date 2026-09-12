"""Dedicated Meeting Intelligence transcription worker service."""

from __future__ import annotations

import json
import os
from uuid import uuid4

from rkjo_meeting_intelligence.application.transcription import TranscriptionStatus
from rkjo_meeting_intelligence.domain.models import TranscriptSegment
from rkjo_meeting_intelligence.infrastructure.audio_storage import LocalAudioStorage
from rkjo_meeting_intelligence.infrastructure.postgres_repository import PostgresMeetingRepository
from rkjo_meeting_intelligence.infrastructure.transcription_repository import PostgresTranscriptionRepository


TRANSCRIPTION_QUEUE = "rkjo.meeting.transcription"


class MeetingTranscriptionWorker:
    def __init__(self, *, job_repository, meeting_repository, storage, provider) -> None:
        self.job_repository = job_repository
        self.meeting_repository = meeting_repository
        self.storage = storage
        self.provider = provider

    def process_message(self, raw_message: str):
        payload = json.loads(raw_message)
        job = self.job_repository.get(
            tenant_id=payload["tenant_id"],
            meeting_id=payload["meeting_id"],
            job_id=payload["job_id"],
        )
        if job is None:
            raise LookupError("Transcription job not found.")

        running = job.transition(TranscriptionStatus.RUNNING)
        self.job_repository.save(running)

        try:
            assets = self.meeting_repository.list_audio_assets(
                tenant_id=job.tenant_id,
                meeting_id=job.meeting_id,
            )
            asset = next(item for item in assets if item.asset_id == job.asset_id)
            content = self.storage.read(storage_key=asset.storage_key)
            segments = self.provider.transcribe(
                content=content,
                filename=asset.original_filename,
                content_type=asset.content_type,
            )
            for item in segments:
                self.meeting_repository.save_transcript_segment(
                    TranscriptSegment(
                        segment_id=str(uuid4()),
                        meeting_id=job.meeting_id,
                        tenant_id=job.tenant_id,
                        text=item.text,
                        start_seconds=item.start_seconds,
                        end_seconds=item.end_seconds,
                        speaker_id=item.speaker_id,
                        confidence=item.confidence,
                    )
                )
            completed = running.transition(TranscriptionStatus.COMPLETED)
            self.job_repository.save(completed)
            return completed
        except Exception as exc:
            failed = running.transition(TranscriptionStatus.FAILED, error=str(exc))
            self.job_repository.save(failed)
            return failed


def build_default_worker(provider):
    database_url = os.getenv(
        "RKJO_DATABASE_URL",
        "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
    )
    audio_root = os.getenv("RKJO_MEETING_AUDIO_ROOT", "/tmp/rkjo-meeting-audio")
    return MeetingTranscriptionWorker(
        job_repository=PostgresTranscriptionRepository(database_url),
        meeting_repository=PostgresMeetingRepository(database_url),
        storage=LocalAudioStorage(audio_root),
        provider=provider,
    )
