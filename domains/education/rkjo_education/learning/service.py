from __future__ import annotations

from uuid import UUID

from .models import Competency, Enrollment, LearningProgress
from .repository import LearningRepository


class DuplicateEnrollmentError(ValueError):
    pass


class LearningService:
    def __init__(self, repository: LearningRepository) -> None:
        self._repository = repository

    def enroll(
        self,
        *,
        tenant_id: UUID,
        learner_id: UUID,
        curriculum_id: UUID,
    ) -> Enrollment:
        existing = self._repository.find_enrollment(
            tenant_id=tenant_id,
            learner_id=learner_id,
            curriculum_id=curriculum_id,
        )
        if existing is not None:
            raise DuplicateEnrollmentError("learner is already enrolled in curriculum")

        enrollment = Enrollment(
            tenant_id=tenant_id,
            learner_id=learner_id,
            curriculum_id=curriculum_id,
        )
        return self._repository.save_enrollment(enrollment)

    def create_competency(
        self,
        *,
        tenant_id: UUID,
        code: str,
        label: str,
    ) -> Competency:
        code = code.strip()
        label = label.strip()
        if not code or not label:
            raise ValueError("code and label are required")
        competency = Competency(tenant_id=tenant_id, code=code, label=label)
        return self._repository.save_competency(competency)

    def record_progress(
        self,
        *,
        tenant_id: UUID,
        learner_id: UUID,
        course_id: UUID,
        completion_percent: int,
        competency_scores: dict[str, int] | None = None,
    ) -> LearningProgress:
        progress = self._repository.find_progress(
            tenant_id=tenant_id,
            learner_id=learner_id,
            course_id=course_id,
        )
        if progress is None:
            progress = LearningProgress(
                tenant_id=tenant_id,
                learner_id=learner_id,
                course_id=course_id,
            )

        progress.set_completion(completion_percent)
        for code, score in (competency_scores or {}).items():
            progress.record_competency(code, score)
        return self._repository.save_progress(progress)
