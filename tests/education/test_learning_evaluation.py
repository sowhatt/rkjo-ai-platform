from uuid import uuid4

from rkjo_education.assessment.models import (
    Assessment,
    Attempt,
    AttemptAnswerEvidence,
    Question,
)
from rkjo_education.assessment.repository import InMemoryAssessmentRepository
from rkjo_education.intelligence.learning_evaluation import (
    LearningEvaluationService,
)
from rkjo_education.intelligence.proof_application import ProofApplicationService
from rkjo_education.intelligence.proof_repository import (
    InMemoryProofChallengeRepository,
)
from rkjo_education.policy import AssistanceLevel


def setup_evaluation():
    tenant_id = uuid4()
    learner_id = uuid4()

    source = Question(
        tenant_id=tenant_id,
        prompt="2 + 3 ?",
        correct_answer="5",
        competency_code="MATH.ADD",
    )

    verification = Question(
        tenant_id=tenant_id,
        prompt="4 + 1 ?",
        correct_answer="5",
        competency_code="MATH.ADD",
    )

    assessment = Assessment(
        tenant_id=tenant_id,
        course_id=uuid4(),
        title="Addition",
        questions=[source, verification],
    )

    assessments = InMemoryAssessmentRepository()
    assessments.save_assessment(assessment)

    proofs = InMemoryProofChallengeRepository()

    proof_service = ProofApplicationService(
        assessment_repository=assessments,
        proof_repository=proofs,
    )

    evaluation = LearningEvaluationService(
        proof_service=proof_service,
    )

    return (
        evaluation,
        assessment,
        tenant_id,
        learner_id,
        source,
        verification,
        proofs,
    )


def test_assisted_correct_answer_creates_proof_challenge():
    (
        evaluation,
        assessment,
        tenant_id,
        learner_id,
        source,
        verification,
        proofs,
    ) = setup_evaluation()

    attempt = Attempt(
        tenant_id=tenant_id,
        assessment_id=assessment.id,
        learner_id=learner_id,
    )

    attempt.answer(
        source.id,
        "5",
        evidence=AttemptAnswerEvidence(
            assistance_level=AssistanceLevel.STRONG_HINT,
            hints_used=1,
            attempt_count=1,
        ),
    )
    attempt.submit(assessment)

    results = evaluation.evaluate_attempt(
        assessment=assessment,
        attempt=attempt,
    )

    assert len(results) == 1

    result = results[0]

    assert result.correct is True
    assert result.mastery == "developing"
    assert result.proof_required is True
    assert result.proof_challenge_id is not None

    stored = proofs.get(
        tenant_id=tenant_id,
        challenge_id=result.proof_challenge_id,
    )

    assert stored is not None
    assert stored.source_question_id == source.id
    assert stored.verification_question_id == verification.id


def test_independent_correct_answer_is_provisional_and_requires_proof():
    (
        evaluation,
        assessment,
        tenant_id,
        learner_id,
        source,
        _,
        _,
    ) = setup_evaluation()

    attempt = Attempt(
        tenant_id=tenant_id,
        assessment_id=assessment.id,
        learner_id=learner_id,
    )

    attempt.answer(
        source.id,
        "5",
        evidence=AttemptAnswerEvidence(
            assistance_level=AssistanceLevel.NONE,
            hints_used=0,
            attempt_count=1,
        ),
    )
    attempt.submit(assessment)

    results = evaluation.evaluate_attempt(
        assessment=assessment,
        attempt=attempt,
    )

    result = results[0]

    assert result.autonomy_score == 100
    assert result.independently_correct is True
    assert result.mastery == "provisional"
    assert result.proof_required is True
    assert result.proof_challenge_id is not None


def test_no_equivalent_question_does_not_create_invalid_challenge():
    tenant_id = uuid4()
    learner_id = uuid4()

    source = Question(
        tenant_id=tenant_id,
        prompt="2 + 3 ?",
        correct_answer="5",
        competency_code="MATH.ADD",
    )

    assessment = Assessment(
        tenant_id=tenant_id,
        course_id=uuid4(),
        title="Addition",
        questions=[source],
    )

    assessments = InMemoryAssessmentRepository()
    assessments.save_assessment(assessment)

    proof_service = ProofApplicationService(
        assessment_repository=assessments,
        proof_repository=InMemoryProofChallengeRepository(),
    )

    evaluation = LearningEvaluationService(
        proof_service=proof_service,
    )

    attempt = Attempt(
        tenant_id=tenant_id,
        assessment_id=assessment.id,
        learner_id=learner_id,
    )

    attempt.answer(
        source.id,
        "5",
        evidence=AttemptAnswerEvidence(
            assistance_level=AssistanceLevel.STRONG_HINT,
        ),
    )
    attempt.submit(assessment)

    result = evaluation.evaluate_attempt(
        assessment=assessment,
        attempt=attempt,
    )[0]

    assert result.proof_required is True
    assert result.proof_challenge_id is None
