from datetime import UTC, datetime

import pytest

from rkjo_meeting_intelligence.application.transcription import (
    STTSegment,
    TranscriptionJob,
    TranscriptionStatus,
)
from rkjo_meeting_intelligence.infrastructure.transcription_repository import (
    InMemoryTranscriptionRepository,
)


def make_job() -> TranscriptionJob:
    return TranscriptionJob.queued(
        job_id="job-1",
        tenant_id="tenant-1",
        meeting_id="meeting-1",
        asset_id="asset-1",
    )


def test_transcription_job_lifecycle():
    job = make_job()
    assert job.status == TranscriptionStatus.QUEUED

    running = job.transition(TranscriptionStatus.RUNNING)
    assert running.status == TranscriptionStatus.RUNNING

    completed = running.transition(TranscriptionStatus.COMPLETED)
    assert completed.status == TranscriptionStatus.COMPLETED

    with pytest.raises(ValueError, match="Invalid transcription transition"):
        completed.transition(TranscriptionStatus.RUNNING)


def test_transcription_failure_records_error():
    running = make_job().transition(TranscriptionStatus.RUNNING)
    failed = running.transition(
        TranscriptionStatus.FAILED,
        error="provider unavailable",
    )
    assert failed.status == TranscriptionStatus.FAILED
    assert failed.error == "provider unavailable"


def test_in_memory_repository_is_tenant_scoped():
    repository = InMemoryTranscriptionRepository()
    job = make_job()
    repository.save(job)

    assert repository.get(
        tenant_id="tenant-1",
        meeting_id="meeting-1",
        job_id="job-1",
    ) == job
    assert repository.get(
        tenant_id="tenant-2",
        meeting_id="meeting-1",
        job_id="job-1",
    ) is None


def test_stt_segment_contract():
    segment = STTSegment(
        text="Bonjour RKJO",
        start_seconds=0.0,
        end_seconds=1.5,
        confidence=0.99,
    )
    assert segment.text == "Bonjour RKJO"
