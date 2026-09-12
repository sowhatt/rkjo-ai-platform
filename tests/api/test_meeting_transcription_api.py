from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from rkjo_api.main import app
from rkjo_api.meeting import get_meeting_repository
from rkjo_api.meeting_transcription import (
    get_transcription_bus,
    get_transcription_repository,
)
from rkjo_meeting_intelligence.domain.models import AudioAsset, Meeting
from rkjo_meeting_intelligence.infrastructure.memory_repository import InMemoryMeetingRepository
from rkjo_meeting_intelligence.infrastructure.transcription_repository import InMemoryTranscriptionRepository


client = TestClient(app)


class FakeBus:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []
        self.closed = False

    def publish(self, queue_name: str, message: str) -> None:
        self.messages.append((queue_name, message))

    def close(self) -> None:
        self.closed = True


def test_create_and_read_transcription_job(monkeypatch):
    meeting_repository = InMemoryMeetingRepository()
    transcription_repository = InMemoryTranscriptionRepository()
    bus = FakeBus()

    meeting_repository.save(
        Meeting(
            meeting_id="meeting-tx-api",
            tenant_id="tenant-tx-api",
            title="Transcription API",
            created_by="owner",
        )
    )
    meeting_repository.save_audio_asset(
        AudioAsset(
            asset_id="asset-tx-api",
            meeting_id="meeting-tx-api",
            tenant_id="tenant-tx-api",
            original_filename="meeting.wav",
            content_type="audio/wav",
            size_bytes=100,
            sha256="b" * 64,
            storage_key="tenant-tx-api/meeting-tx-api/asset-tx-api/meeting.wav",
            created_at=datetime.now(UTC),
        )
    )

    app.dependency_overrides[get_meeting_repository] = lambda: meeting_repository
    app.dependency_overrides[get_transcription_repository] = lambda: transcription_repository
    app.dependency_overrides[get_transcription_bus] = lambda: bus

    api_key = "tx-api-key"
    monkeypatch.setenv("RKJO_OPERATOR_API_KEY", api_key)
    monkeypatch.setenv("RKJO_OPERATOR_TENANT_ID", "tenant-tx-api")
    headers = {"X-API-Key": api_key}

    try:
        created = client.post(
            "/meetings/meeting-tx-api/transcriptions",
            headers=headers,
            json={"asset_id": "asset-tx-api"},
        )
        assert created.status_code == 202
        body = created.json()
        assert body["asset_id"] == "asset-tx-api"
        assert body["status"] == "queued"
        assert len(bus.messages) == 1
        assert bus.messages[0][0] == "rkjo.meeting.transcription"
        assert bus.closed is True

        read = client.get(
            f"/meetings/meeting-tx-api/transcriptions/{body['job_id']}",
            headers=headers,
        )
        assert read.status_code == 200
        assert read.json()["job_id"] == body["job_id"]
        assert read.json()["status"] == "queued"
    finally:
        app.dependency_overrides.pop(get_meeting_repository, None)
        app.dependency_overrides.pop(get_transcription_repository, None)
        app.dependency_overrides.pop(get_transcription_bus, None)


def test_transcription_rejects_unknown_audio_asset(monkeypatch):
    meeting_repository = InMemoryMeetingRepository()
    transcription_repository = InMemoryTranscriptionRepository()
    bus = FakeBus()
    meeting_repository.save(
        Meeting(
            meeting_id="meeting-no-asset",
            tenant_id="tenant-no-asset",
            title="No asset",
            created_by="owner",
        )
    )

    app.dependency_overrides[get_meeting_repository] = lambda: meeting_repository
    app.dependency_overrides[get_transcription_repository] = lambda: transcription_repository
    app.dependency_overrides[get_transcription_bus] = lambda: bus

    api_key = "tx-no-asset-key"
    monkeypatch.setenv("RKJO_OPERATOR_API_KEY", api_key)
    monkeypatch.setenv("RKJO_OPERATOR_TENANT_ID", "tenant-no-asset")

    try:
        response = client.post(
            "/meetings/meeting-no-asset/transcriptions",
            headers={"X-API-Key": api_key},
            json={"asset_id": "missing"},
        )
        assert response.status_code == 404
        assert bus.messages == []
    finally:
        app.dependency_overrides.pop(get_meeting_repository, None)
        app.dependency_overrides.pop(get_transcription_repository, None)
        app.dependency_overrides.pop(get_transcription_bus, None)
