from uuid import uuid4

import pytest

from rkjo_education.assessment.models import Assessment, Question
from rkjo_education.assessment.repository import (
    InMemoryAssessmentRepository,
)
from rkjo_education.intelligence import (
    InMemoryProofChallengeRepository,
    ProofStatus,
)
from rkjo_education.intelligence.proof_application import (
    ProofApplicationService,
    ProofChallengeCompletedError,
    ProofChallengeNotFoundError,
)


def setup_service():
    tenant_id = uuid4()
    learner_id = uuid4()
    course_id = uuid4()

    source = Question(
        tenant_id=tenant_id,
        prompt="2x + 5 = 15",
        correct_answer="5",
        competency_code="ALG.EQUATION",
    )

    verification = Question(
        tenant_id=tenant_id,
        prompt="3x + 4 = 19",
        correct_answer="5",
        competency_code="ALG.EQUATION",
    )

    assessment = Assessment(
        tenant_id=tenant_id,
        course_id=course_id,
        title="Equations",
        questions=[source, verification],
    )

    assessments = InMemoryAssessmentRepository()
    assessments.save_assessment(assessment)

    proofs = InMemoryProofChallengeRepository()

    service = ProofApplicationService(
        assessment_repository=assessments,
        proof_repository=proofs,
    )

    return (
        service,
        tenant_id,
        learner_id,
        assessment,
        source,
        verification,
        proofs,
    )


def test_create_valid_challenge():
    (
        service,
        tenant_id,
        learner_id,
        assessment,
        source,
        verification,
        _,
    ) = setup_service()

    challenge = service.create_challenge(
        tenant_id=tenant_id,
        learner_id=learner_id,
        assessment_id=assessment.id,
        source_question_id=source.id,
        verification_question_id=verification.id,
    )

    assert challenge.status == ProofStatus.REQUIRED
    assert challenge.competency_code == "ALG.EQUATION"
    assert challenge.course_id == assessment.course_id


def test_create_rejects_different_competency():
    (
        service,
        tenant_id,
        learner_id,
        assessment,
        source,
        verification,
        _,
    ) = setup_service()

    verification.competency_code = "GEO.AREA"

    with pytest.raises(ValueError, match="same competency"):
        service.create_challenge(
            tenant_id=tenant_id,
            learner_id=learner_id,
            assessment_id=assessment.id,
            source_question_id=source.id,
            verification_question_id=verification.id,
        )


def test_get_verification_question():
    (
        service,
        tenant_id,
        learner_id,
        assessment,
        source,
        verification,
        _,
    ) = setup_service()

    challenge = service.create_challenge(
        tenant_id=tenant_id,
        learner_id=learner_id,
        assessment_id=assessment.id,
        source_question_id=source.id,
        verification_question_id=verification.id,
    )

    question = service.get_verification_question(
        tenant_id=tenant_id,
        challenge_id=challenge.id,
    )

    assert question.id == verification.id
    assert question.prompt == "3x + 4 = 19"


def test_correct_answer_passes_proof():
    (
        service,
        tenant_id,
        learner_id,
        assessment,
        source,
        verification,
        proofs,
    ) = setup_service()

    challenge = service.create_challenge(
        tenant_id=tenant_id,
        learner_id=learner_id,
        assessment_id=assessment.id,
        source_question_id=source.id,
        verification_question_id=verification.id,
    )

    result = service.submit(
        tenant_id=tenant_id,
        challenge_id=challenge.id,
        answer="5",
    )

    assert result.status == ProofStatus.PASSED
    assert result.independently_verified is True

    stored = proofs.get(
        tenant_id=tenant_id,
        challenge_id=challenge.id,
    )

    assert stored is not None
    assert stored.status == ProofStatus.PASSED
    assert stored.completed_at is not None


def test_wrong_answer_fails_proof():
    (
        service,
        tenant_id,
        learner_id,
        assessment,
        source,
        verification,
        _,
    ) = setup_service()

    challenge = service.create_challenge(
        tenant_id=tenant_id,
        learner_id=learner_id,
        assessment_id=assessment.id,
        source_question_id=source.id,
        verification_question_id=verification.id,
    )

    result = service.submit(
        tenant_id=tenant_id,
        challenge_id=challenge.id,
        answer="7",
    )

    assert result.status == ProofStatus.FAILED
    assert result.independently_verified is False


def test_completed_challenge_cannot_be_resubmitted():
    (
        service,
        tenant_id,
        learner_id,
        assessment,
        source,
        verification,
        _,
    ) = setup_service()

    challenge = service.create_challenge(
        tenant_id=tenant_id,
        learner_id=learner_id,
        assessment_id=assessment.id,
        source_question_id=source.id,
        verification_question_id=verification.id,
    )

    service.submit(
        tenant_id=tenant_id,
        challenge_id=challenge.id,
        answer="5",
    )

    with pytest.raises(
        ProofChallengeCompletedError,
        match="already completed",
    ):
        service.submit(
            tenant_id=tenant_id,
            challenge_id=challenge.id,
            answer="5",
        )


def test_challenge_is_tenant_scoped():
    (
        service,
        tenant_id,
        learner_id,
        assessment,
        source,
        verification,
        _,
    ) = setup_service()

    challenge = service.create_challenge(
        tenant_id=tenant_id,
        learner_id=learner_id,
        assessment_id=assessment.id,
        source_question_id=source.id,
        verification_question_id=verification.id,
    )

    with pytest.raises(ProofChallengeNotFoundError):
        service.submit(
            tenant_id=uuid4(),
            challenge_id=challenge.id,
            answer="5",
        )
