from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from rkjo_education.assessment.models import (
    Attempt,
    AttemptAnswerEvidence,
)
from rkjo_education.assessment.service import AssessmentService

from .learning_evaluation import (
    LearningEvaluationService,
    QuestionLearningResult,
)


@dataclass(frozen=True, slots=True)
class AssessmentLearningResult:
    attempt: Attempt
    learning: list[QuestionLearningResult]


class AssessmentLearningService:
    def __init__(
        self,
        *,
        assessment_service: AssessmentService,
        learning_evaluation_service: LearningEvaluationService,
    ) -> None:
        self._assessment_service = assessment_service
        self._learning_evaluation_service = learning_evaluation_service

    def submit_attempt(
        self,
        *,
        tenant_id: UUID,
        attempt_id: UUID,
        answers: dict[UUID, str],
        evidence: dict[UUID, AttemptAnswerEvidence] | None = None,
    ) -> AssessmentLearningResult:
        attempt = self._assessment_service.submit_attempt(
            tenant_id=tenant_id,
            attempt_id=attempt_id,
            answers=answers,
            evidence=evidence,
        )

        assessment = self._assessment_service.get_assessment(
            tenant_id=tenant_id,
            assessment_id=attempt.assessment_id,
        )

        learning = self._learning_evaluation_service.evaluate_attempt(
            assessment=assessment,
            attempt=attempt,
        )

        return AssessmentLearningResult(
            attempt=attempt,
            learning=learning,
        )
