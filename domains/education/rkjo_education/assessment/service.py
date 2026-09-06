from __future__ import annotations

from uuid import UUID

from .models import Assessment, Attempt, Question
from .repository import AssessmentRepository


class AssessmentNotFoundError(LookupError):
    pass


class AttemptNotFoundError(LookupError):
    pass


class AssessmentService:
    def __init__(self, repository: AssessmentRepository) -> None:
        self._repository = repository

    def create_assessment(
        self,
        *,
        tenant_id: UUID,
        course_id: UUID,
        title: str,
        questions: list[dict],
    ) -> Assessment:
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("title is required")
        assessment = Assessment(
            tenant_id=tenant_id,
            course_id=course_id,
            title=normalized_title,
        )
        for item in questions:
            assessment.add_question(
                Question(
                    tenant_id=tenant_id,
                    prompt=item["prompt"],
                    correct_answer=item["correct_answer"],
                    points=item.get("points", 1),
                    competency_code=item.get("competency_code"),
                )
            )
        if not assessment.questions:
            raise ValueError("assessment requires at least one question")
        return self._repository.save_assessment(assessment)

    def get_assessment(self, *, tenant_id: UUID, assessment_id: UUID) -> Assessment:
        assessment = self._repository.get_assessment(
            tenant_id=tenant_id,
            assessment_id=assessment_id,
        )
        if assessment is None:
            raise AssessmentNotFoundError("assessment not found")
        return assessment

    def start_attempt(
        self,
        *,
        tenant_id: UUID,
        assessment_id: UUID,
        learner_id: UUID,
    ) -> Attempt:
        self.get_assessment(tenant_id=tenant_id, assessment_id=assessment_id)
        return self._repository.save_attempt(
            Attempt(
                tenant_id=tenant_id,
                assessment_id=assessment_id,
                learner_id=learner_id,
            )
        )

    def submit_attempt(
        self,
        *,
        tenant_id: UUID,
        attempt_id: UUID,
        answers: dict[UUID, str],
    ) -> Attempt:
        attempt = self._repository.get_attempt(
            tenant_id=tenant_id,
            attempt_id=attempt_id,
        )
        if attempt is None:
            raise AttemptNotFoundError("attempt not found")
        assessment = self.get_assessment(
            tenant_id=tenant_id,
            assessment_id=attempt.assessment_id,
        )
        for question_id, answer in answers.items():
            attempt.answer(question_id, answer)
        attempt.submit(assessment)
        return self._repository.save_attempt(attempt)
