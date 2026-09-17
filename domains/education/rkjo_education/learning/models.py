from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EnrollmentStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class Competency:
    tenant_id: UUID
    code: str
    label: str
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class Enrollment:
    tenant_id: UUID
    learner_id: UUID
    curriculum_id: UUID
    id: UUID = field(default_factory=uuid4)
    status: EnrollmentStatus = EnrollmentStatus.ACTIVE
    enrolled_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class LearningProgress:
    tenant_id: UUID
    learner_id: UUID
    course_id: UUID
    id: UUID = field(default_factory=uuid4)
    completion_percent: int = 0
    competency_scores: dict[str, int] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=utc_now)

    def set_completion(self, completion_percent: int) -> None:
        if not 0 <= completion_percent <= 100:
            raise ValueError("completion_percent must be between 0 and 100")
        self.completion_percent = completion_percent
        self.updated_at = utc_now()

    def record_competency(self, competency_code: str, score: int) -> None:
        if not 0 <= score <= 100:
            raise ValueError("competency score must be between 0 and 100")
        code = competency_code.strip()
        if not code:
            raise ValueError("competency_code is required")
        self.competency_scores[code] = score
        self.updated_at = utc_now()
