"""Stream C+F: verified evidence drives the next learning action."""
from uuid import uuid4
import pytest

from rkjo_education.assessment.models import Assessment, Attempt, AttemptAnswerEvidence, Question
from rkjo_education.intelligence.proof import ProofResult, ProofStatus
from rkjo_education.intelligence.proof_repository import StoredProofChallenge
from rkjo_education.learning.assessment_action_bridge import decide_after_assessment
from rkjo_education.learning.next_action_policy import NextAction


def scenario(*, correct=True, hints=0, answered=True):
    tenant, learner, course = uuid4(), uuid4(), uuid4()
    question = Question(tenant_id=tenant, prompt="2+2 ?", correct_answer="4",
                        competency_code="MATH.4")
    assessment = Assessment(tenant_id=tenant, course_id=course,
                            title="Mathématiques", questions=[question])
    attempt = Attempt(tenant_id=tenant, learner_id=learner,
                      assessment_id=assessment.id)
    if answered:
        attempt.answer(question.id, "4" if correct else "5",
                       evidence=AttemptAnswerEvidence(hints_used=hints))
    attempt.submit(assessment)
    params = dict(tenant_id=tenant, learner_id=learner, assessment=assessment,
                  attempt=attempt, question_id=question.id)
    return params


def passed_proof(p):
    question = p["assessment"].questions[0]
    challenge = StoredProofChallenge(
        tenant_id=p["tenant_id"], learner_id=p["learner_id"],
        course_id=p["assessment"].course_id,
        competency_code=question.competency_code,
        source_question_id=question.id, verification_question_id=uuid4(),
        status=ProofStatus.PASSED,
    )
    result = ProofResult(status=ProofStatus.PASSED,
                         competency_code=question.competency_code,
                         independently_verified=True)
    return challenge, result


@pytest.mark.parametrize("args,expected", [
    (dict(answered=False), NextAction.DIAGNOSE),
    (dict(correct=False), NextAction.PRACTICE),
    (dict(correct=True, hints=2), NextAction.AUTONOMOUS_PROOF),
    (dict(correct=True, hints=0), NextAction.AUTONOMOUS_PROOF),
])
def test_observed_assessment_outcomes(args, expected):
    assert decide_after_assessment(**scenario(**args)).action == expected


def test_prerequisites_override_success():
    assert decide_after_assessment(
        **scenario(), missing_prerequisites=True,
    ).action == NextAction.REMEDIATE


def test_verified_independent_proof_advances():
    p = scenario(correct=True, hints=2)
    challenge, result = passed_proof(p)
    decision = decide_after_assessment(
        **p, proof_challenge=challenge, proof_result=result,
    )
    assert decision.action == NextAction.ADVANCE
    assert decision.reason


def test_proof_ownership_mismatch_fails_closed():
    p = scenario()
    challenge, result = passed_proof(p)
    challenge.learner_id = uuid4()
    with pytest.raises(ValueError, match="proof does not match"):
        decide_after_assessment(**p, proof_challenge=challenge, proof_result=result)


def test_proof_competency_mismatch_fails_closed():
    p = scenario()
    challenge, result = passed_proof(p)
    result = ProofResult(status=result.status, competency_code="OTHER",
                         independently_verified=True)
    with pytest.raises(ValueError, match="proof does not match"):
        decide_after_assessment(**p, proof_challenge=challenge, proof_result=result)


def test_unverified_or_failed_proof_cannot_advance():
    p = scenario()
    challenge, result = passed_proof(p)
    result = ProofResult(status=ProofStatus.PASSED,
                         competency_code=result.competency_code,
                         independently_verified=False)
    assert decide_after_assessment(
        **p, proof_challenge=challenge, proof_result=result,
    ).action == NextAction.AUTONOMOUS_PROOF
    challenge.status = ProofStatus.FAILED
    result = ProofResult(status=ProofStatus.FAILED,
                         competency_code=result.competency_code,
                         independently_verified=False)
    assert decide_after_assessment(
        **p, proof_challenge=challenge, proof_result=result,
    ).action == NextAction.AUTONOMOUS_PROOF


def test_attempt_must_be_submitted_and_tenant_bound():
    p = scenario()
    p["attempt"].status = "in_progress"
    with pytest.raises(ValueError, match="submitted"):
        decide_after_assessment(**p)
    p["attempt"].status = "submitted"
    with pytest.raises(ValueError, match="tenant mismatch"):
        decide_after_assessment(**{**p, "tenant_id": uuid4()})


def test_no_proof_result_without_challenge():
    p = scenario()
    _, result = passed_proof(p)
    with pytest.raises(ValueError, match="together"):
        decide_after_assessment(**p, proof_result=result)
