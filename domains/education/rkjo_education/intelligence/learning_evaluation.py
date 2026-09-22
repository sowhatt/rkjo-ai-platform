from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from rkjo_education.assessment.models import Assessment, Attempt, Question

from .autonomy import AutonomyCalculator
from .mastery import MasteryCalculator, MasteryObservation
from .proof import ProofOfLearningService
from .proof_application import ProofApplicationService


@dataclass(frozen=True, slots=True)
class QuestionLearningResult:
    question_id: UUID
    competency_code: str
    correct: bool
    autonomy_score: int
    independently_correct: bool
    mastery: str
    proof_required: bool
    proof_challenge_id: UUID | None


class LearningEvaluationService:
    def __init__(
        self,
        *,
        proof_service: ProofApplicationService,
    ) -> None:
        self._proof_service = proof_service
        self._autonomy = AutonomyCalculator()
        self._mastery = MasteryCalculator()
        self._proof_rules = ProofOfLearningService()

    def evaluate_attempt(
        self,
        *,
        assessment: Assessment,
        attempt: Attempt,
    ) -> list[QuestionLearningResult]:
        results: list[QuestionLearningResult] = []

        for question in assessment.questions:
            if question.id not in attempt.answers:
                continue

            competency_code = question.competency_code
            if not competency_code:
                continue

            submitted_answer = attempt.answers[question.id]
            correct = (
                submitted_answer.strip().casefold()
                == question.correct_answer.strip().casefold()
            )

            autonomy = self._autonomy.from_attempt_evidence(
                correct=correct,
                evidence=attempt.evidence.get(question.id),
            )

            mastery = self._mastery.calculate(
                [
                    MasteryObservation(
                        correct=correct,
                        autonomy=autonomy,
                    )
                ]
            )

            proof_required = self._proof_rules.required(mastery)
            proof_challenge_id: UUID | None = None

            if proof_required:
                verification = self._verification_question(
                    assessment=assessment,
                    source=question,
                )

                if verification is not None:
                    challenge = self._proof_service.create_challenge(
                        tenant_id=attempt.tenant_id,
                        learner_id=attempt.learner_id,
                        assessment_id=assessment.id,
                        source_question_id=question.id,
                        verification_question_id=verification.id,
                    )
                    proof_challenge_id = challenge.id

            results.append(
                QuestionLearningResult(
                    question_id=question.id,
                    competency_code=competency_code,
                    correct=correct,
                    autonomy_score=autonomy.score,
                    independently_correct=autonomy.independently_correct,
                    mastery=mastery.level.value,
                    proof_required=proof_required,
                    proof_challenge_id=proof_challenge_id,
                )
            )

        return results

    @staticmethod
    def _verification_question(
        *,
        assessment: Assessment,
        source: Question,
    ) -> Question | None:
        if not source.competency_code:
            return None

        candidates = [
            question
            for question in assessment.questions
            if question.id != source.id
            and question.competency_code == source.competency_code
        ]

        if not candidates:
            return None

        return sorted(
            candidates,
            key=lambda question: str(question.id),
        )[0]
