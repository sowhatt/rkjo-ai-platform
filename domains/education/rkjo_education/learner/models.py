from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LearnerStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


@dataclass(slots=True)
class LearnerProfile:
    tenant_id: UUID
    first_name: str
    last_name: str
    level: str
    id: UUID = field(default_factory=uuid4)
    status: LearnerStatus = LearnerStatus.ACTIVE
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def rename(self, *, first_name: str, last_name: str) -> None:
        self.first_name = first_name.strip()
        self.last_name = last_name.strip()
        self.updated_at = utc_now()

    def change_level(self, level: str) -> None:
        self.level = level.strip()
        self.updated_at = utc_now()
