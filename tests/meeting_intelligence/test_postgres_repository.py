import os
import uuid
from datetime import UTC, datetime

import psycopg
import pytest

from rkjo_meeting_intelligence.domain.models import (
    ActionItem,
    AudioAsset,
    Decision,
    Meeting,
    MeetingStatus,
    Participant,
    TranscriptSegment,
)
from rkjo_meeting_intelligence.infrastructure.postgres_repository import PostgresMeetingRepository

DATABASE_URL = os.getenv(
    "RKJO_DATABASE_URL",
    "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
)


@pytest.fixture()
def repository():
    try:
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute("SELECT 1")
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL is unavailable.")
    return PostgresMeetingRepository(DATABASE_URL)


def test_meeting_survives_repository_recreation(repository):
    suffix = uuid.uuid4().hex[:8]
    meeting = Meeting(
        meeting_id=f"meeting-{suffix}",
        tenant_id=f"tenant-{suffix}",
        title="Comite strategique",
        created_by="user-1",
        scheduled_at=datetime(2026, 9, 12, 14, 0, tzinfo=UTC),
    )
    repository.save(meeting)
    recreated = PostgresMeetingRepository(DATABASE_URL)
    assert recreated.get(tenant_id=meeting.tenant_id, meeting_id=meeting.meeting_id) == meeting


def test_meeting_is_tenant_safe(repository):
    suffix = uuid.uuid4().hex[:8]
    meeting = Meeting(
        meeting_id=f"meeting-{suffix}",
        tenant_id=f"tenant-a-{suffix}",
        title="Confidentiel",
        created_by="user-a",
    )
    repository.save(meeting)
    assert repository.get(tenant_id=f"tenant-b-{suffix}", meeting_id=meeting.meeting_id) is None


def test_audio_asset_survives_repository_recreation(repository):
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"tenant-audio-{suffix}"
    meeting_id = f"meeting-audio-{suffix}"
    repository.save(Meeting(meeting_id, tenant_id, "Audio", "owner"))
    asset = AudioAsset(
        asset_id=f"asset-{suffix}",
        meeting_id=meeting_id,
        tenant_id=tenant_id,
        original_filename="codir.wav",
        content_type="audio/wav",
        size_bytes=1024,
        sha256="a" * 64,
        storage_key=f"{tenant_id}/{meeting_id}/asset-{suffix}/codir.wav",
        created_at=datetime.now(UTC),
    )
    repository.save_audio_asset(asset)

    recreated = PostgresMeetingRepository(DATABASE_URL)
    assert recreated.list_audio_assets(
        tenant_id=tenant_id,
        meeting_id=meeting_id,
    ) == [asset]
    assert recreated.list_audio_assets(
        tenant_id=f"other-{tenant_id}",
        meeting_id=meeting_id,
    ) == []


def test_full_meeting_record_is_persisted(repository):
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"tenant-{suffix}"
    meeting_id = f"meeting-{suffix}"
    repository.save(Meeting(meeting_id, tenant_id, "CODIR", "owner", MeetingStatus.REVIEW))
    repository.save_participant(Participant("p1", meeting_id, tenant_id, "Alice", "DG", "alice@example.com"))
    repository.save_transcript_segment(TranscriptSegment("s1", meeting_id, tenant_id, "Nous validons le budget.", 10.0, 15.0, "p1", 0.98))
    repository.save_decision(Decision("d1", meeting_id, tenant_id, "Budget valide", "s1"))
    repository.save_action(ActionItem("a1", meeting_id, tenant_id, "Envoyer le budget", "s1", "p1"))

    assert len(repository.list_participants(tenant_id=tenant_id, meeting_id=meeting_id)) == 1
    assert len(repository.list_transcript_segments(tenant_id=tenant_id, meeting_id=meeting_id)) == 1
    assert len(repository.list_decisions(tenant_id=tenant_id, meeting_id=meeting_id)) == 1
    assert len(repository.list_actions(tenant_id=tenant_id, meeting_id=meeting_id)) == 1


def test_listing_is_tenant_safe(repository):
    suffix = uuid.uuid4().hex[:8]
    tenant_a = f"tenant-a-{suffix}"
    tenant_b = f"tenant-b-{suffix}"
    repository.save(Meeting(f"a-{suffix}", tenant_a, "A", "owner"))
    repository.save(Meeting(f"b-{suffix}", tenant_b, "B", "owner"))
    ids = {item.meeting_id for item in repository.list_for_tenant(tenant_id=tenant_a)}
    assert f"a-{suffix}" in ids
    assert f"b-{suffix}" not in ids
