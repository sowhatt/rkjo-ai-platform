"""In-memory Meeting repository."""

from __future__ import annotations

from rkjo_meeting_intelligence.domain.models import Meeting


class InMemoryMeetingRepository:
    def __init__(self) -> None:
        self._meetings: dict[
            tuple[str, str],
            Meeting,
        ] = {}

    def save(
        self,
        meeting: Meeting,
    ) -> Meeting:
        key = (
            meeting.tenant_id,
            meeting.meeting_id,
        )

        self._meetings[key] = meeting

        return meeting

    def get(
        self,
        *,
        tenant_id: str,
        meeting_id: str,
    ) -> Meeting | None:
        return self._meetings.get(
            (
                tenant_id.strip(),
                meeting_id.strip(),
            )
        )

    def list_for_tenant(
        self,
        *,
        tenant_id: str,
    ) -> list[Meeting]:
        normalized_tenant_id = tenant_id.strip()

        meetings = [
            meeting
            for (
                stored_tenant_id,
                _,
            ),
            meeting
            in self._meetings.items()
            if stored_tenant_id
            == normalized_tenant_id
        ]

        return sorted(
            meetings,
            key=lambda meeting: meeting.meeting_id,
        )
