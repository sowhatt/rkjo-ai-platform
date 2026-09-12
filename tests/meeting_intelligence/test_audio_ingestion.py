from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from rkjo_api.main import app
from rkjo_api.meeting import get_meeting_repository
from rkjo_api.meeting_audio import get_audio_storage
from rkjo_meeting_intelligence.domain.models import AudioAsset, Meeting
from rkjo_meeting_intelligence.infrastructure.audio_storage import LocalAudioStorage
from rkjo_meeting_intelligence.infrastructure.memory_repository import InMemoryMeetingRepository


client = TestClient(app)


def test_audio_asset_validates_hash_and_size():
    with pytest.raises(ValueError, match="size_bytes"):
        AudioAsset(
            asset_id="asset-1",
            meeting_id="meeting-1",
            tenant_id="tenant-1",
            original_filename="meeting.wav",
            content_type="audio/wav",
            size_bytes=0,
            sha256="a" * 64,
            storage_key="tenant-1/meeting-1/asset-1/meeting.wav",
            created_at=datetime.now(UTC),
        )

    with pytest.raises(ValueError, match="sha256"):
        AudioAsset(
            asset_id="asset-1",
            meeting_id="meeting-1",
            tenant_id="tenant-1",
            original_filename="meeting.wav",
            content_type="audio/wav",
            size_bytes=3,
            sha256="not-a-hash",
            storage_key="tenant-1/meeting-1/asset-1/meeting.wav",
            created_at=datetime.now(UTC),
        )


def test_local_audio_storage_is_tenant_scoped(tmp_path):
    storage = LocalAudioStorage(tmp_path)
    key = storage.save(
        tenant_id="tenant-a",
        meeting_id="meeting-a",
        asset_id="asset-a",
        filename="../meeting.wav",
        content=b"audio-bytes",
    )

    assert key == "tenant-a/meeting-a/asset-a/meeting.wav"
    assert (tmp_path / key).read_bytes() == b"audio-bytes"


def test_operator_can_upload_and_list_audio(monkeypatch, tmp_path):
    repository = InMemoryMeetingRepository()
    repository.save(
        Meeting(
            meeting_id="meeting-audio-api",
            tenant_id="tenant-audio-api",
            title="Audio meeting",
            created_by="operator",
        )
    )
    storage = LocalAudioStorage(tmp_path)

    app.dependency_overrides[get_meeting_repository] = lambda: repository
    app.dependency_overrides[get_audio_storage] = lambda: storage

    api_key = "meeting-audio-operator"
    monkeypatch.setenv("RKJO_OPERATOR_API_KEY", api_key)
    monkeypatch.setenv("RKJO_OPERATOR_TENANT_ID", "tenant-audio-api")
    headers = {"X-API-Key": api_key}

    try:
        payload = b"RIFF-rkjo-test-audio"
        response = client.post(
            "/meetings/meeting-audio-api/audio",
            headers=headers,
            files={"file": ("meeting.wav", payload, "audio/wav")},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["original_filename"] == "meeting.wav"
        assert body["content_type"] == "audio/wav"
        assert body["size_bytes"] == len(payload)
        assert body["sha256"] == hashlib.sha256(payload).hexdigest()
        assert (tmp_path / body["storage_key"]).read_bytes() == payload

        listed = client.get(
            "/meetings/meeting-audio-api/audio",
            headers=headers,
        )
        assert listed.status_code == 200
        assert [item["asset_id"] for item in listed.json()] == [body["asset_id"]]
    finally:
        app.dependency_overrides.pop(get_meeting_repository, None)
        app.dependency_overrides.pop(get_audio_storage, None)


def test_audio_upload_rejects_non_media(monkeypatch, tmp_path):
    repository = InMemoryMeetingRepository()
    repository.save(
        Meeting(
            meeting_id="meeting-audio-reject",
            tenant_id="tenant-audio-reject",
            title="Reject media",
            created_by="operator",
        )
    )

    app.dependency_overrides[get_meeting_repository] = lambda: repository
    app.dependency_overrides[get_audio_storage] = lambda: LocalAudioStorage(tmp_path)

    api_key = "meeting-audio-reject-key"
    monkeypatch.setenv("RKJO_OPERATOR_API_KEY", api_key)
    monkeypatch.setenv("RKJO_OPERATOR_TENANT_ID", "tenant-audio-reject")

    try:
        response = client.post(
            "/meetings/meeting-audio-reject/audio",
            headers={"X-API-Key": api_key},
            files={"file": ("notes.txt", b"not audio", "text/plain")},
        )
        assert response.status_code == 415
    finally:
        app.dependency_overrides.pop(get_meeting_repository, None)
        app.dependency_overrides.pop(get_audio_storage, None)
