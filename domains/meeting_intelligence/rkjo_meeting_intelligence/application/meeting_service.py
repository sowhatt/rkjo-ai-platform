"""Application service for meeting lifecycle management."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from rkjo_meeting_intelligence.domain.models import (
    Meeting,
    MeetingStatus,
)


_ALLOWED_TRANSITIONS: dict[
    MeetingStatus,
    set[MeetingStatus],
] = {
    MeetingStatus.DRAFT: {
        MeetingStatus.RECORDING,
        MeetingStatus.ARCHIVED,
    },
    MeetingStatus.RECORDING: {
        MeetingStatus.PROCESSING,
        MeetingStatus.ARCHIVED,
    },
    MeetingStatus.PROCESSING: {
        MeetingStatus.REVIEW,
        MeetingStatus.ARCHIVED,
    },
    MeetingStatus.REVIEW: {
        MeetingStatus.VALIDATED,
        MeetingStatus.PROCESSING,
        MeetingStatus.ARCHIVED,
    },
    MeetingStatus.VALIDATED: {
        MeetingStatus.ARCHIVED,
    },
    MeetingStatus.ARCHIVED: set(),
}


class InvalidMeetingTransition(ValueError):
    """Raised when a meeting lifecycle transition is not allowed."""


class MeetingService:
    def transition(
        self,
        meeting: Meeting,
        target_status: MeetingStatus,
        *,
        occurred_at: datetime | None = None,
    ) -> Meeting:
        if target_status == meeting.status:
            return meeting

        allowed = _ALLOWED_TRANSITIONS[
            meeting.status
        ]

        if target_status not in allowed:
            raise InvalidMeetingTransition(
                "Invalid meeting transition: "
                f"{meeting.status.value} -> "
                f"{target_status.value}"
            )

        timestamp = occurred_at

        if target_status == MeetingStatus.RECORDING:
            return replace(
                meeting,
                status=target_status,
                started_at=(
                    timestamp
                    if timestamp is not None
                    else meeting.started_at
                ),
            )

        if (
            meeting.status == MeetingStatus.RECORDING
            and target_status
            == MeetingStatus.PROCESSING
        ):
            return replace(
                meeting,
                status=target_status,
                ended_at=(
                    timestamp
                    if timestamp is not None
                    else meeting.ended_at
                ),
            )

        return replace(
            meeting,
            status=target_status,
        )

    def start_recording(
        self,
        meeting: Meeting,
        *,
        started_at: datetime,
    ) -> Meeting:
        return self.transition(
            meeting,
            MeetingStatus.RECORDING,
            occurred_at=started_at,
        )

    def stop_recording(
        self,
        meeting: Meeting,
        *,
        ended_at: datetime,
    ) -> Meeting:
        return self.transition(
            meeting,
            MeetingStatus.PROCESSING,
            occurred_at=ended_at,
        )

    def mark_ready_for_review(
        self,
        meeting: Meeting,
    ) -> Meeting:
        return self.transition(
            meeting,
            MeetingStatus.REVIEW,
        )

    def validate(
        self,
        meeting: Meeting,
    ) -> Meeting:
        return self.transition(
            meeting,
            MeetingStatus.VALIDATED,
        )

    def archive(
        self,
        meeting: Meeting,
    ) -> Meeting:
        return self.transition(
            meeting,
            MeetingStatus.ARCHIVED,
        )
