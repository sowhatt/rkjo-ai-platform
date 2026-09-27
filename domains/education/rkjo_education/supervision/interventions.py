from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TeacherInterventionType(StrEnum):
    REQUEST_NEW_PROOF = "request_new_proof"
    ASSIGN_CONSOLIDATION = "assign_consolidation"
    SEND_MESSAGE = "send_message"


class TeacherInterventionStatus(StrEnum):
    REQUESTED = "requested"


class TeacherIntervention(BaseModel):
    intervention_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    learner_id: UUID
    intervention_type: TeacherInterventionType
    message: str | None = None
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: TeacherInterventionStatus = TeacherInterventionStatus.REQUESTED


class TeacherInterventionStore:
    """Tenant-scoped intervention command store for the supervision MVP."""

    def __init__(self) -> None:
        self._items: dict[tuple[UUID, UUID], list[TeacherIntervention]] = {}

    def create(self, intervention: TeacherIntervention) -> TeacherIntervention:
        key = (intervention.tenant_id, intervention.learner_id)
        self._items.setdefault(key, []).append(intervention)
        return intervention.model_copy(deep=True)

    def list_for_learner(self, *, tenant_id: UUID, learner_id: UUID) -> list[TeacherIntervention]:
        return [item.model_copy(deep=True) for item in self._items.get((tenant_id, learner_id), [])]
