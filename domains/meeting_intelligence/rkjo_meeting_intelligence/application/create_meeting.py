"""Meeting creation use case."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from rkjo_meeting_intelligence.domain.models import (
    Meeting,
)
from rkjo_meeting_intelligence.domain.repository import (
    MeetingRepository,
)


MeetingIdFactory = Callable[[], str]


class CreateMeetingService:
    def __init__(
        self,
        *,
        repository: MeetingRepository,
        meeting_id_factory: MeetingIdFactory | None = None,
    ) -> None:
        self._repository = repository
        self._meeting_id_factory = (
            meeting_id_factory
            or (lambda: str(uuid4()))
        )

    def create(
        self,
        *,
        tenant_id: str,
        title: str,
        created_by: str,
        scheduled_at: datetime | None = None,
    ) -> Meeting:
        meeting = Meeting(
            meeting_id=(
                self._meeting_id_factory()
            ),
            tenant_id=tenant_id,
            title=title,
            created_by=created_by,
            scheduled_at=scheduled_at,
        )

        return self._repository.save(
            meeting
        )
