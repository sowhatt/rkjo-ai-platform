from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LearnerSupervisionState(BaseModel):
    """Current pedagogical state derived from the learner event stream."""

    tenant_id: UUID
    learner_id: UUID
    course_id: UUID | None = None
    session_id: UUID | None = None
    assessment_id: UUID | None = None
    active: bool = False
    last_event_at: datetime | None = None
    last_event_id: UUID | None = None
    answers_submitted: int = Field(default=0, ge=0)
    hints_requested: int = Field(default=0, ge=0)
    tutor_requests: int = Field(default=0, ge=0)
    autonomy_score: int | None = Field(default=None, ge=0, le=100)
    mastery: str | None = None
    proof_status: str | None = None
