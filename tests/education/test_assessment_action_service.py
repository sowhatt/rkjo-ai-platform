"""Integration at repository-service boundary; no API or PostgreSQL required."""
from uuid import uuid4

import pytest

from rkjo_education.assessment.models import Assessment, Attempt, Question
from rkjo_education.assessment.repository import InMemoryAssessmentRepository
from rkjo_education.intelligence.proof import ProofStatus
from rkjo_education.intelligence.proof_repository import (
    InMemoryProofChallengeRepository, StoredProofChallenge,
)
from rkjo_education.learning.assessment_action_service import (
    AssessmentActionService, EvidenceNotFoundError,
)
from rkjo_education.learning.next_action_policy import NextAction


def setup():
    tenant, learner, course = uuid4(), uuid4(), uuid4()
    question = Question(tenant_id=tenant, prompt="2+2?", correct_answer="4",
                        competency_code="ARITHMETIC")
    assessment = Assessment(tenant_id=tenant, course_id=course,
                            title="Test", questions=[question])
    attempt = Attempt(tenant_id=tenant, learner_id=learner,
                      assessment_id=assessment.id)
    attempt.answer(question.id, "4")
    attempt.submit(assessment)
    assessments = InMemoryAssessmentRepository()
    proofs = InMemoryProofChallengeRepository()
    assessments.save_assessment(assessment)
    assessments.save_attempt(attempt)
    service = AssessmentActionService(assessments=assessments, proofs=proofs)
    return tenant, learner, assessment, attempt, question, proofs, service


def test_repository_records_control_decision():
    tenant, learner, _, attempt, question, _, service = setup()
    assert service.recommend(tenant_id=tenant, learner_id=learner,
                            attempt_id=attempt.id,
                            question_id=question.id).action == NextAction.AUTONOMOUS_PROOF


def test_verified_proof_from_repository_allows_advance():
    tenant, learner, assessment, attempt, question, proofs, service = setup()
    proof = StoredProofChallenge(
        tenant_id=tenant, learner_id=learner, course_id=assessment.course_id,
        competency_code="ARITHMETIC", source_question_id=question.id,
        verification_question_id=uuid4(), status=ProofStatus.PASSED)
    proofs.save(proof)
    decision = service.recommend(
        tenant_id=tenant, learner_id=learner, attempt_id=attempt.id,
        question_id=question.id, proof_challenge_id=proof.id)
    assert decision.action == NextAction.ADVANCE


def test_failed_proof_does_not_advance():
    tenant, learner, assessment, attempt, question, proofs, service = setup()
    proof = StoredProofChallenge(
        tenant_id=tenant, learner_id=learner, course_id=assessment.course_id,
        competency_code="ARITHMETIC", source_question_id=question.id,
        verification_question_id=uuid4(), status=ProofStatus.FAILED)
    proofs.save(proof)
    assert service.recommend(
        tenant_id=tenant, learner_id=learner, attempt_id=attempt.id,
        question_id=question.id, proof_challenge_id=proof.id,
    ).action == NextAction.AUTONOMOUS_PROOF


@pytest.mark.parametrize("foreign", ["tenant", "learner"])
def test_cross_identity_attempt_is_not_found(foreign):
    tenant, learner, _, attempt, question, _, service = setup()
    if foreign == "tenant":
        tenant = uuid4()
    else:
        learner = uuid4()
    with pytest.raises(EvidenceNotFoundError):
        service.recommend(tenant_id=tenant, learner_id=learner,
                          attempt_id=attempt.id, question_id=question.id)


def test_unowned_proof_is_not_found():
    tenant, learner, assessment, attempt, question, proofs, service = setup()
    proof = StoredProofChallenge(
        tenant_id=tenant, learner_id=uuid4(), course_id=assessment.course_id,
        competency_code="ARITHMETIC", source_question_id=question.id,
        verification_question_id=uuid4(), status=ProofStatus.PASSED)
    proofs.save(proof)
    with pytest.raises(EvidenceNotFoundError):
        service.recommend(tenant_id=tenant, learner_id=learner,
                          attempt_id=attempt.id, question_id=question.id,
                          proof_challenge_id=proof.id)


def test_prerequisites_remain_blocking():
    tenant, learner, _, attempt, question, _, service = setup()
    assert service.recommend(
        tenant_id=tenant, learner_id=learner, attempt_id=attempt.id,
        question_id=question.id, missing_prerequisites=True,
    ).action == NextAction.REMEDIATE
