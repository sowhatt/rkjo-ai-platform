from datetime import datetime, timezone

import pytest

from rkjo_meeting_intelligence.application.meeting_service import (
    InvalidMeetingTransition,
    MeetingService,
)
from rkjo_meeting_intelligence.domain.models import (
    Meeting,
    MeetingStatus,
)


def build_meeting() -> Meeting:
    return Meeting(
        meeting_id="meeting-1",
        tenant_id="tenant-1",
        title="Comité projet",
        created_by="user-1",
    )


def test_start_recording_moves_draft_to_recording():
    service = MeetingService()
    started_at = datetime(
        2026,
        9,
        5,
        9,
        0,
        tzinfo=timezone.utc,
    )

    meeting = service.start_recording(
        build_meeting(),
        started_at=started_at,
    )

    assert meeting.status == MeetingStatus.RECORDING
    assert meeting.started_at == started_at


def test_stop_recording_moves_to_processing():
    service = MeetingService()
    started_at = datetime(
        2026,
        9,
        5,
        9,
        0,
        tzinfo=timezone.utc,
    )
    ended_at = datetime(
        2026,
        9,
        5,
        10,
        0,
        tzinfo=timezone.utc,
    )

    meeting = service.start_recording(
        build_meeting(),
        started_at=started_at,
    )

    meeting = service.stop_recording(
        meeting,
        ended_at=ended_at,
    )

    assert meeting.status == MeetingStatus.PROCESSING
    assert meeting.ended_at == ended_at


def test_processing_can_move_to_review():
    service = MeetingService()

    meeting = Meeting(
        meeting_id="meeting-1",
        tenant_id="tenant-1",
        title="Réunion",
        created_by="user-1",
        status=MeetingStatus.PROCESSING,
    )

    reviewed = service.mark_ready_for_review(
        meeting
    )

    assert reviewed.status == MeetingStatus.REVIEW


def test_review_can_be_validated():
    service = MeetingService()

    meeting = Meeting(
        meeting_id="meeting-1",
        tenant_id="tenant-1",
        title="Réunion",
        created_by="user-1",
        status=MeetingStatus.REVIEW,
    )

    validated = service.validate(meeting)

    assert (
        validated.status
        == MeetingStatus.VALIDATED
    )


def test_invalid_transition_is_rejected():
    service = MeetingService()

    with pytest.raises(
        InvalidMeetingTransition,
        match="draft -> validated",
    ):
        service.validate(
            build_meeting()
        )


def test_archived_meeting_cannot_be_reopened():
    service = MeetingService()

    meeting = Meeting(
        meeting_id="meeting-1",
        tenant_id="tenant-1",
        title="Réunion",
        created_by="user-1",
        status=MeetingStatus.ARCHIVED,
    )

    with pytest.raises(
        InvalidMeetingTransition
    ):
        service.transition(
            meeting,
            MeetingStatus.RECORDING,
        )
