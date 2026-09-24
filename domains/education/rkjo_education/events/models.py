from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EducationEventType(StrEnum):
    SESSION_STARTED = "learner.session.started"
    ASSESSMENT_STARTED = "learner.assessment.started"
    ANSWER_SUBMITTED = "learner.answer.submitted"
    HINT_REQUESTED = "learner.hint.requested"
    TUTOR_REQUESTED = "learner.tutor.requested"
    ASSESSMENT_COMPLETED = "learner.assessment.completed"
    MASTERY_UPDATED = "learner.mastery.updated"
    AUTONOMY_UPDATED = "learner.autonomy.updated"
    PROOF_REQUESTED = "learner.proof.requested"
    PROOF_PASSED = "learner.proof.passed"
    PROOF_FAILED = "learner.proof.failed"
    SESSION_COMPLETED = "learner.session.completed"


class EducationLearningEvent(BaseModel):
    """Canonical, tenant-safe pedagogical event envelope."""

    event_id: UUID = Field(default_factory=uuid4)
    event_type: EducationEventType
    tenant_id: UUID
    learner_id: UUID
    course_id: UUID | None = None
    session_id: UUID | None = None
    assessment_id: UUID | None = None
    question_id: UUID | None = None
    competency_code: str | None = Field(default=None, max_length=120)
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    payload: dict[str, Any] = Field(default_factory=dict)
