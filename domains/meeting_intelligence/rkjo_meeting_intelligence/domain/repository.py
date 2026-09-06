"""Repository contracts for Meeting Intelligence."""

from __future__ import annotations

from typing import Protocol

from rkjo_meeting_intelligence.domain.models import Meeting


class MeetingRepository(Protocol):
    def save(self, meeting: Meeting) -> Meeting:
        ...

    def get(
        self,
        *,
        tenant_id: str,
        meeting_id: str,
    ) -> Meeting | None:
        ...

    def list_for_tenant(
        self,
        *,
        tenant_id: str,
    ) -> list[Meeting]:
        ...
