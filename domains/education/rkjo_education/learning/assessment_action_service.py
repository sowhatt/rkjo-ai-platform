"""Tenant-scoped application service for evidence-backed Next Best Action.

The API layer must derive tenant_id and learner_id from authenticated server
identity, not untrusted browser parameters. No proof status is accepted from
the client; it is reloaded from the repository.
"""
from __future__ import annotations

from uuid import UUID

from rkjo_education.assessment.repository import AssessmentRepository
from rkjo_education.intelligence.proof import ProofResult, ProofStatus
from rkjo_education.intelligence.proof_repository import ProofChallengeRepository
from rkjo_education.learning.assessment_action_bridge import decide_after_assessment
from rkjo_education.learning.next_action_policy import ActionDecision


class EvidenceNotFoundError(LookupError):
    """No matching tenant-bound evidence was found."""


class AssessmentActionService:
    def __init__(
        self,
        *,
        assessments: AssessmentRepository,
        proofs: ProofChallengeRepository,
    ) -> None:
        self._assessments = assessments
        self._proofs = proofs

    def recommend(
        self,
        *,
        tenant_id: UUID,
        learner_id: UUID,
        attempt_id: UUID,
        question_id: UUID,
        proof_challenge_id: UUID | None = None,
        missing_prerequisites: bool = False,
    ) -> ActionDecision:
        attempt = self._assessments.get_attempt(
            tenant_id=tenant_id, attempt_id=attempt_id,
        )
        if attempt is None or attempt.learner_id != learner_id:
            raise EvidenceNotFoundError("attempt not found")
        assessment = self._assessments.get_assessment(
            tenant_id=tenant_id, assessment_id=attempt.assessment_id,
        )
        if assessment is None:
            raise EvidenceNotFoundError("assessment not found")

        challenge = None
        result = None
        if proof_challenge_id is not None:
            challenge = self._proofs.get(
                tenant_id=tenant_id, challenge_id=proof_challenge_id,
            )
            if challenge is None or challenge.learner_id != learner_id:
                raise EvidenceNotFoundError("proof challenge not found")
            # Proof status is reloaded from trusted tenant-scoped storage.
            # The existing ProofApplicationService sets PASSED only after a
            # separate, independently correct verification question.
            result = ProofResult(
                status=challenge.status,
                competency_code=challenge.competency_code,
                independently_verified=challenge.status == ProofStatus.PASSED,
            )
        return decide_after_assessment(
            tenant_id=tenant_id,
            learner_id=learner_id,
            assessment=assessment,
            attempt=attempt,
            question_id=question_id,
            missing_prerequisites=missing_prerequisites,
            proof_challenge=challenge,
            proof_result=result,
        )
