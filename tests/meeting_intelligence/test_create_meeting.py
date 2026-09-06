from datetime import datetime, timezone

from rkjo_meeting_intelligence.application.create_meeting import (
    CreateMeetingService,
)
from rkjo_meeting_intelligence.domain.models import (
    MeetingStatus,
)
from rkjo_meeting_intelligence.infrastructure.memory_repository import (
    InMemoryMeetingRepository,
)


def test_create_meeting_persists_draft():
    repository = (
        InMemoryMeetingRepository()
    )

    service = CreateMeetingService(
        repository=repository,
        meeting_id_factory=(
            lambda: "meeting-123"
        ),
    )

    meeting = service.create(
        tenant_id="tenant-1",
        title="Comité de direction",
        created_by="user-42",
    )

    assert (
        meeting.meeting_id
        == "meeting-123"
    )
    assert (
        meeting.status
        == MeetingStatus.DRAFT
    )

    stored = repository.get(
        tenant_id="tenant-1",
        meeting_id="meeting-123",
    )

    assert stored == meeting


def test_create_meeting_keeps_schedule():
    repository = (
        InMemoryMeetingRepository()
    )

    service = CreateMeetingService(
        repository=repository,
        meeting_id_factory=(
            lambda: "meeting-1"
        ),
    )

    scheduled_at = datetime(
        2026,
        9,
        7,
        9,
        30,
        tzinfo=timezone.utc,
    )

    meeting = service.create(
        tenant_id="tenant-1",
        title="Réunion projet",
        created_by="user-1",
        scheduled_at=scheduled_at,
    )

    assert (
        meeting.scheduled_at
        == scheduled_at
    )


def test_create_meeting_preserves_tenant_scope():
    repository = (
        InMemoryMeetingRepository()
    )

    service = CreateMeetingService(
        repository=repository,
        meeting_id_factory=(
            lambda: "meeting-shared"
        ),
    )

    service.create(
        tenant_id="tenant-a",
        title="Réunion A",
        created_by="user-a",
    )

    assert (
        repository.get(
            tenant_id="tenant-b",
            meeting_id="meeting-shared",
        )
        is None
    )
