from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .models import Competency, Enrollment, LearningProgress


class LearningRepository(Protocol):
    def save_enrollment(self, enrollment: Enrollment) -> Enrollment: ...

    def find_enrollment(
        self, *, tenant_id: UUID, learner_id: UUID, curriculum_id: UUID
    ) -> Enrollment | None: ...

    def save_competency(self, competency: Competency) -> Competency: ...

    def list_competencies(self, *, tenant_id: UUID) -> list[Competency]: ...

    def save_progress(self, progress: LearningProgress) -> LearningProgress: ...

    def find_progress(
        self, *, tenant_id: UUID, learner_id: UUID, course_id: UUID
    ) -> LearningProgress | None: ...


class InMemoryLearningRepository:
    def __init__(self) -> None:
        self._enrollments: dict[tuple[UUID, UUID, UUID], Enrollment] = {}
        self._competencies: dict[tuple[UUID, UUID], Competency] = {}
        self._progress: dict[tuple[UUID, UUID, UUID], LearningProgress] = {}

    def save_enrollment(self, enrollment: Enrollment) -> Enrollment:
        self._enrollments[
            (enrollment.tenant_id, enrollment.learner_id, enrollment.curriculum_id)
        ] = enrollment
        return enrollment

    def find_enrollment(
        self, *, tenant_id: UUID, learner_id: UUID, curriculum_id: UUID
    ) -> Enrollment | None:
        return self._enrollments.get((tenant_id, learner_id, curriculum_id))

    def save_competency(self, competency: Competency) -> Competency:
        self._competencies[(competency.tenant_id, competency.id)] = competency
        return competency

    def list_competencies(self, *, tenant_id: UUID) -> list[Competency]:
        return [
            competency
            for (stored_tenant_id, _), competency in self._competencies.items()
            if stored_tenant_id == tenant_id
        ]

    def save_progress(self, progress: LearningProgress) -> LearningProgress:
        self._progress[
            (progress.tenant_id, progress.learner_id, progress.course_id)
        ] = progress
        return progress

    def find_progress(
        self, *, tenant_id: UUID, learner_id: UUID, course_id: UUID
    ) -> LearningProgress | None:
        return self._progress.get((tenant_id, learner_id, course_id))
