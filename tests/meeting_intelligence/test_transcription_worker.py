from __future__ import annotations

import json
from pathlib import Path

from rkjo_meeting_intelligence.application.transcription import (
    STTSegment,
    TranscriptionJob,
    TranscriptionStatus,
)
from rkjo_meeting_intelligence.domain.models import AudioAsset, Meeting
from rkjo_meeting_intelligence.infrastructure.audio_storage import LocalAudioStorage
from rkjo_meeting_intelligence.infrastructure.memory_repository import InMemoryMeetingRepository
from rkjo_meeting_intelligence.infrastructure.transcription_repository import InMemoryTranscriptionRepository
from rkjo_worker.meeting_transcription_worker import MeetingTranscriptionWorker


class FakeProvider:
    def transcribe(self, *, content: bytes, filename: str, content_type: str):
        assert content == b"fake-audio"
        assert filename == "meeting.wav"
        assert content_type == "audio/wav"
        return [
            STTSegment(
                text="Bonjour RKJO",
                start_seconds=0.0,
                end_seconds=1.4,
                speaker_id="speaker-1",
                confidence=0.98,
            )
        ]


class FailingProvider:
    def transcribe(self, *, content: bytes, filename: str, content_type: str):
        raise RuntimeError("STT provider unavailable")


def build_fixture(tmp_path: Path, provider):
    meeting_repository = InMemoryMeetingRepository()
    job_repository = InMemoryTranscriptionRepository()
    storage = LocalAudioStorage(tmp_path)

    meeting = Meeting(
        meeting_id="meeting-1",
        tenant_id="tenant-1",
        title="CODIR",
        created_by="owner",
    )
    meeting_repository.save(meeting)

    storage_key = storage.save(
        tenant_id="tenant-1",
        meeting_id="meeting-1",
        asset_id="asset-1",
        filename="meeting.wav",
        content=b"fake-audio",
    )
    meeting_repository.save_audio_asset(
        AudioAsset(
            asset_id="asset-1",
            meeting_id="meeting-1",
            tenant_id="tenant-1",
            original_filename="meeting.wav",
            content_type="audio/wav",
            size_bytes=10,
            sha256="a" * 64,
            storage_key=storage_key,
            created_at=meeting.scheduled_at or __import__("datetime").datetime.now(__import__("datetime").UTC),
        )
    )

    job = TranscriptionJob.queued(
        job_id="job-1",
        tenant_id="tenant-1",
        meeting_id="meeting-1",
        asset_id="asset-1",
    )
    job_repository.save(job)

    worker = MeetingTranscriptionWorker(
        job_repository=job_repository,
        meeting_repository=meeting_repository,
        storage=storage,
        provider=provider,
    )
    message = json.dumps(
        {
            "job_id": "job-1",
            "tenant_id": "tenant-1",
            "meeting_id": "meeting-1",
            "asset_id": "asset-1",
        }
    )
    return worker, job_repository, meeting_repository, message


def test_worker_creates_transcript_segments(tmp_path):
    worker, job_repository, meeting_repository, message = build_fixture(
        tmp_path,
        FakeProvider(),
    )
    completed = worker.process_message(message)

    assert completed.status == TranscriptionStatus.COMPLETED
    stored = job_repository.get(
        tenant_id="tenant-1",
        meeting_id="meeting-1",
        job_id="job-1",
    )
    assert stored.status == TranscriptionStatus.COMPLETED
    segments = meeting_repository.list_transcript_segments(
        tenant_id="tenant-1",
        meeting_id="meeting-1",
    )
    assert len(segments) == 1
    assert segments[0].text == "Bonjour RKJO"
    assert segments[0].speaker_id == "speaker-1"


def test_worker_marks_job_failed_when_provider_fails(tmp_path):
    worker, job_repository, meeting_repository, message = build_fixture(
        tmp_path,
        FailingProvider(),
    )
    failed = worker.process_message(message)

    assert failed.status == TranscriptionStatus.FAILED
    assert failed.error == "STT provider unavailable"
    assert meeting_repository.list_transcript_segments(
        tenant_id="tenant-1",
        meeting_id="meeting-1",
    ) == []
