from __future__ import annotations

from uuid import UUID
from pydantic import BaseModel, Field


class ReferentialCompetency(BaseModel):
    code: str
    label: str
    keywords: tuple[str, ...] = ()
    importance: int = Field(default=1, ge=1, le=3)


class AlignmentCandidate(BaseModel):
    competency_code: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class AlignmentDecision(BaseModel):
    source_id: UUID
    candidate: AlignmentCandidate | None
    requires_learner_confirmation: bool
