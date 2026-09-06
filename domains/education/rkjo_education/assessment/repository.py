from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .models import Assessment, Attempt


class AssessmentRepository(Protocol):
    def save_assessment(self, assessment: Assessment) -> Assessment: ...
    def get_assessment(self, *, tenant_id: UUID, assessment_id: UUID) -> Assessment | None: ...
    def save_attempt(self, attempt: Attempt) -> Attempt: ...
    def get_attempt(self, *, tenant_id: UUID, attempt_id: UUID) -> Attempt | None: ...


class InMemoryAssessmentRepository:
    def __init__(self) -> None:
        self._assessments: dict[tuple[UUID, UUID], Assessment] = {}
        self._attempts: dict[tuple[UUID, UUID], Attempt] = {}

    def save_assessment(self, assessment: Assessment) -> Assessment:
        self._assessments[(assessment.tenant_id, assessment.id)] = assessment
        return assessment

    def get_assessment(self, *, tenant_id: UUID, assessment_id: UUID) -> Assessment | None:
        return self._assessments.get((tenant_id, assessment_id))

    def save_attempt(self, attempt: Attempt) -> Attempt:
        self._attempts[(attempt.tenant_id, attempt.id)] = attempt
        return attempt

    def get_attempt(self, *, tenant_id: UUID, attempt_id: UUID) -> Attempt | None:
        return self._attempts.get((tenant_id, attempt_id))
