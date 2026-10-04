from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .models import Assessment, Attempt, Question


class AssessmentRepository(Protocol):
    def save_assessment(self, assessment: Assessment) -> Assessment: ...
    def get_assessment(self, *, tenant_id: UUID, assessment_id: UUID) -> Assessment | None: ...
    def list_assessments(
        self,
        *,
        tenant_id: UUID,
        course_id: UUID,
    ) -> list[Assessment]: ...

    def list_submitted_assessment_ids(
        self,
        *,
        tenant_id: UUID,
        learner_id: UUID,
        course_id: UUID,
    ) -> set[UUID]: ...

    def get_question(
        self,
        *,
        tenant_id: UUID,
        question_id: UUID,
    ) -> Question | None: ...
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

    def list_assessments(
        self,
        *,
        tenant_id: UUID,
        course_id: UUID,
    ) -> list[Assessment]:
        return [
            assessment
            for (item_tenant_id, _), assessment in self._assessments.items()
            if item_tenant_id == tenant_id and assessment.course_id == course_id
        ]

    def list_submitted_assessment_ids(
        self,
        *,
        tenant_id: UUID,
        learner_id: UUID,
        course_id: UUID,
    ) -> set[UUID]:
        course_assessment_ids = {
            assessment.id
            for assessment in self.list_assessments(
                tenant_id=tenant_id,
                course_id=course_id,
            )
        }
        return {
            attempt.assessment_id
            for (item_tenant_id, _), attempt in self._attempts.items()
            if item_tenant_id == tenant_id
            and attempt.learner_id == learner_id
            and attempt.assessment_id in course_assessment_ids
            and attempt.status.value == "submitted"
        }

    def get_question(
        self,
        *,
        tenant_id: UUID,
        question_id: UUID,
    ) -> Question | None:
        for (item_tenant_id, _), assessment in self._assessments.items():
            if item_tenant_id != tenant_id:
                continue
            for question in assessment.questions:
                if question.id == question_id:
                    return question
        return None

    def save_attempt(self, attempt: Attempt) -> Attempt:
        self._attempts[(attempt.tenant_id, attempt.id)] = attempt
        return attempt

    def get_attempt(self, *, tenant_id: UUID, attempt_id: UUID) -> Attempt | None:
        return self._attempts.get((tenant_id, attempt_id))
