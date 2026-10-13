"""Bridge verified assessment evidence to the deterministic Next Best Action policy.

This module does not authenticate callers or load records: the application layer
must fetch tenant-scoped, learner-owned records from trusted repositories.
"""
from __future__ import annotations

from uuid import UUID

from rkjo_education.assessment.models import Assessment, Attempt, AttemptStatus
from rkjo_education.intelligence.proof import ProofResult, ProofStatus
from rkjo_education.intelligence.proof_repository import StoredProofChallenge
from rkjo_education.learning.next_action_policy import (
    ActionDecision, LearningSignals, recommend_next_action,
)


def decide_after_assessment(
    *,
    tenant_id: UUID,
    learner_id: UUID,
    assessment: Assessment,
    attempt: Attempt,
    question_id: UUID,
    missing_prerequisites: bool = False,
    proof_challenge: StoredProofChallenge | None = None,
    proof_result: ProofResult | None = None,
) -> ActionDecision:
    """Recommend a next action using submitted answers and validated proof only.

    Every input must originate from authorized, tenant-scoped repositories.
    A submitted assessment answer is not an independent proof, even without hints.
    """
    if attempt.tenant_id != tenant_id or assessment.tenant_id != tenant_id:
        raise ValueError("tenant mismatch")
    if attempt.learner_id != learner_id or attempt.assessment_id != assessment.id:
        raise ValueError("learner or assessment mismatch")
    if attempt.status != AttemptStatus.SUBMITTED:
        raise ValueError("attempt must be submitted")
    question = next((q for q in assessment.questions if q.id == question_id), None)
    if question is None or question.tenant_id != tenant_id:
        raise ValueError("question not in assessment")
    if question_id not in attempt.answers:
        return recommend_next_action(LearningSignals(
            assessed=False, missing_prerequisites=missing_prerequisites,
        ))
    answer = attempt.answers[question_id].strip().casefold()
    correct = answer == question.correct_answer.strip().casefold()
    evidence = attempt.evidence.get(question_id)
    hints = evidence.hints_used if evidence is not None else 0

    if (proof_challenge is None) != (proof_result is None):
        raise ValueError("proof challenge and result must be provided together")
    proven = False
    if proof_challenge is not None and proof_result is not None:
        if (proof_challenge.tenant_id != tenant_id
                or proof_challenge.learner_id != learner_id
                or proof_challenge.course_id != assessment.course_id
                or proof_challenge.source_question_id != question_id
                or not question.competency_code
                or proof_challenge.competency_code != question.competency_code
                or proof_result.competency_code != question.competency_code
                or proof_challenge.status != proof_result.status):
            raise ValueError("proof does not match learner, question or competency")
        proven = (proof_challenge.status == ProofStatus.PASSED
                  and proof_result.independently_verified)
    return recommend_next_action(LearningSignals(
        assessed=True,
        last_answer_correct=correct,
        hints_used=hints,
        autonomous_proof_passed=proven,
        missing_prerequisites=missing_prerequisites,
    ))
