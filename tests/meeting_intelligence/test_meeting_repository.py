from rkjo_meeting_intelligence.domain.models import (
    Meeting,
)
from rkjo_meeting_intelligence.infrastructure.memory_repository import (
    InMemoryMeetingRepository,
)


def build_meeting(
    *,
    meeting_id: str,
    tenant_id: str,
) -> Meeting:
    return Meeting(
        meeting_id=meeting_id,
        tenant_id=tenant_id,
        title="Réunion",
        created_by="user-1",
    )


def test_repository_saves_and_reads_meeting():
    repository = (
        InMemoryMeetingRepository()
    )

    meeting = build_meeting(
        meeting_id="meeting-1",
        tenant_id="tenant-1",
    )

    repository.save(meeting)

    stored = repository.get(
        tenant_id="tenant-1",
        meeting_id="meeting-1",
    )

    assert stored == meeting


def test_repository_isolates_tenants():
    repository = (
        InMemoryMeetingRepository()
    )

    repository.save(
        build_meeting(
            meeting_id="meeting-1",
            tenant_id="tenant-a",
        )
    )

    stored = repository.get(
        tenant_id="tenant-b",
        meeting_id="meeting-1",
    )

    assert stored is None


def test_repository_lists_only_tenant_meetings():
    repository = (
        InMemoryMeetingRepository()
    )

    repository.save(
        build_meeting(
            meeting_id="meeting-1",
            tenant_id="tenant-a",
        )
    )
    repository.save(
        build_meeting(
            meeting_id="meeting-2",
            tenant_id="tenant-a",
        )
    )
    repository.save(
        build_meeting(
            meeting_id="meeting-3",
            tenant_id="tenant-b",
        )
    )

    meetings = (
        repository.list_for_tenant(
            tenant_id="tenant-a"
        )
    )

    assert [
        meeting.meeting_id
        for meeting in meetings
    ] == [
        "meeting-1",
        "meeting-2",
    ]
