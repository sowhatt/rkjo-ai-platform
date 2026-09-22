from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from rkjo_education.assessment.models import (
    AttemptAnswerEvidence,
    Question,
)
from rkjo_education.assessment.repository import AssessmentRepository
from rkjo_education.policy.models import AssistanceLevel

from .autonomy import AutonomyCalculator
from .proof import (
    ProofChallenge,
    ProofOfLearningService,
    ProofResult,
    ProofStatus,
)
from .proof_repository import (
    ProofChallengeRepository,
    StoredProofChallenge,
)


class ProofChallengeNotFoundError(LookupError):
    pass


class ProofQuestionNotFoundError(LookupError):
    pass


class ProofChallengeCompletedError(ValueError):
    pass


class ProofApplicationService:
    def __init__(
        self,
        *,
        assessment_repository: AssessmentRepository,
        proof_repository: ProofChallengeRepository,
    ) -> None:
        self._assessment_repository = assessment_repository
        self._proof_repository = proof_repository
        self._proof_service = ProofOfLearningService()
        self._autonomy_calculator = AutonomyCalculator()

    def create_challenge(
        self,
        *,
        tenant_id: UUID,
        learner_id: UUID,
        assessment_id: UUID,
        source_question_id: UUID,
        verification_question_id: UUID,
    ) -> StoredProofChallenge:
        assessment = self._assessment_repository.get_assessment(
            tenant_id=tenant_id,
            assessment_id=assessment_id,
        )
        if assessment is None:
            raise ProofQuestionNotFoundError("assessment not found")

        source = self._find_question_in_assessment(
            assessment.questions,
            source_question_id,
        )
        verification = self._find_question_in_assessment(
            assessment.questions,
            verification_question_id,
        )

        if source.id == verification.id:
            raise ValueError(
                "verification question must differ from source question"
            )

        source_code = (source.competency_code or "").strip()
        verification_code = (
            verification.competency_code or ""
        ).strip()

        if not source_code:
            raise ValueError(
                "source question requires competency_code"
            )

        if not verification_code:
            raise ValueError(
                "verification question requires competency_code"
            )

        if source_code != verification_code:
            raise ValueError(
                "verification question must test the same competency"
            )

        challenge = StoredProofChallenge(
            tenant_id=tenant_id,
            learner_id=learner_id,
            course_id=assessment.course_id,
            competency_code=source_code,
            source_question_id=source.id,
            verification_question_id=verification.id,
        )

        return self._proof_repository.save(challenge)

    def get_challenge(
        self,
        *,
        tenant_id: UUID,
        challenge_id: UUID,
    ) -> StoredProofChallenge:
        challenge = self._proof_repository.get(
            tenant_id=tenant_id,
            challenge_id=challenge_id,
        )

        if challenge is None:
            raise ProofChallengeNotFoundError(
                "proof challenge not found"
            )

        return challenge

    def get_verification_question(
        self,
        *,
        tenant_id: UUID,
        challenge_id: UUID,
    ) -> Question:
        challenge = self.get_challenge(
            tenant_id=tenant_id,
            challenge_id=challenge_id,
        )

        return self._load_verification_question(
            tenant_id=tenant_id,
            challenge=challenge,
        )

    def submit(
        self,
        *,
        tenant_id: UUID,
        challenge_id: UUID,
        answer: str,
    ) -> ProofResult:
        challenge = self.get_challenge(
            tenant_id=tenant_id,
            challenge_id=challenge_id,
        )

        if challenge.status is not ProofStatus.REQUIRED:
            raise ProofChallengeCompletedError(
                "proof challenge is already completed"
            )

        verification = self._load_verification_question(
            tenant_id=tenant_id,
            challenge=challenge,
        )

        verification_code = (
            verification.competency_code or ""
        ).strip()

        if verification_code != challenge.competency_code:
            raise ValueError(
                "verification question must test the same competency"
            )

        correct = (
            answer.strip().casefold()
            == verification.correct_answer.strip().casefold()
        )

        evidence = AttemptAnswerEvidence(
            assistance_level=AssistanceLevel.NONE,
            hints_used=0,
            attempt_count=1,
        )

        autonomy = self._autonomy_calculator.from_attempt_evidence(
            correct=correct,
            evidence=evidence,
        )

        result = self._proof_service.evaluate(
            challenge=ProofChallenge(
                competency_code=challenge.competency_code,
                source_question_id=challenge.source_question_id,
                verification_question_id=(
                    challenge.verification_question_id
                ),
            ),
            verification_competency_code=verification_code,
            correct=correct,
            autonomy=autonomy,
        )

        challenge.status = result.status
        challenge.completed_at = datetime.now(timezone.utc)

        self._proof_repository.save(challenge)

        return result

    def _load_verification_question(
        self,
        *,
        tenant_id: UUID,
        challenge: StoredProofChallenge,
    ) -> Question:
        question = self._assessment_repository.get_question(
            tenant_id=tenant_id,
            question_id=challenge.verification_question_id,
        )

        if question is None:
            raise ProofQuestionNotFoundError(
                "verification question not found"
            )

        return question

    @staticmethod
    def _find_question_in_assessment(
        questions: list[Question],
        question_id: UUID,
    ) -> Question:
        for question in questions:
            if question.id == question_id:
                return question

        raise ProofQuestionNotFoundError(
            "question not found in assessment"
        )
