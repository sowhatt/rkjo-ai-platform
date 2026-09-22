from uuid import uuid4

import pytest

from rkjo_education.intelligence import (
    AutonomyResult,
    MasteryLevel,
    MasteryResult,
    ProofChallenge,
    ProofOfLearningService,
    ProofStatus,
)


def autonomy(
    *,
    independent: bool,
    score: int = 100,
    verification: bool = False,
) -> AutonomyResult:
    return AutonomyResult(
        score=score,
        independently_correct=independent,
        requires_independent_verification=verification,
    )


def mastery(
    level: MasteryLevel,
    *,
    requires_proof: bool,
) -> MasteryResult:
    return MasteryResult(
        level=level,
        correct_observations=1,
        independent_successes=0,
        requires_proof_of_learning=requires_proof,
    )


def test_proof_required_for_developing_assisted_learning():
    result = mastery(
        MasteryLevel.DEVELOPING,
        requires_proof=True,
    )

    assert ProofOfLearningService().required(result) is True


def test_proof_required_for_provisional_mastery():
    result = mastery(
        MasteryLevel.PROVISIONAL,
        requires_proof=True,
    )

    assert ProofOfLearningService().required(result) is True


def test_proof_not_required_after_mastery():
    result = MasteryResult(
        level=MasteryLevel.MASTERED,
        correct_observations=2,
        independent_successes=2,
        requires_proof_of_learning=False,
    )

    assert ProofOfLearningService().required(result) is False


def test_verification_question_must_be_different():
    question_id = uuid4()

    with pytest.raises(
        ValueError,
        match="verification question must differ",
    ):
        ProofChallenge(
            competency_code="MATH.FRACTION",
            source_question_id=question_id,
            verification_question_id=question_id,
        )


def test_competency_is_required():
    with pytest.raises(
        ValueError,
        match="competency_code is required",
    ):
        ProofChallenge(
            competency_code=" ",
            source_question_id=uuid4(),
            verification_question_id=uuid4(),
        )


def test_verification_must_test_same_competency():
    challenge = ProofChallenge(
        competency_code="MATH.FRACTION",
        source_question_id=uuid4(),
        verification_question_id=uuid4(),
    )

    with pytest.raises(
        ValueError,
        match="same competency",
    ):
        ProofOfLearningService().evaluate(
            challenge=challenge,
            verification_competency_code="MATH.GEOMETRY",
            correct=True,
            autonomy=autonomy(independent=True),
        )


def test_correct_independent_verification_passes():
    challenge = ProofChallenge(
        competency_code="MATH.FRACTION",
        source_question_id=uuid4(),
        verification_question_id=uuid4(),
    )

    result = ProofOfLearningService().evaluate(
        challenge=challenge,
        verification_competency_code="MATH.FRACTION",
        correct=True,
        autonomy=autonomy(independent=True),
    )

    assert result.status == ProofStatus.PASSED
    assert result.independently_verified is True


def test_correct_but_assisted_verification_fails():
    challenge = ProofChallenge(
        competency_code="MATH.FRACTION",
        source_question_id=uuid4(),
        verification_question_id=uuid4(),
    )

    result = ProofOfLearningService().evaluate(
        challenge=challenge,
        verification_competency_code="MATH.FRACTION",
        correct=True,
        autonomy=autonomy(
            independent=False,
            score=70,
        ),
    )

    assert result.status == ProofStatus.FAILED
    assert result.independently_verified is False


def test_wrong_independent_answer_fails():
    challenge = ProofChallenge(
        competency_code="MATH.FRACTION",
        source_question_id=uuid4(),
        verification_question_id=uuid4(),
    )

    result = ProofOfLearningService().evaluate(
        challenge=challenge,
        verification_competency_code="MATH.FRACTION",
        correct=False,
        autonomy=autonomy(independent=False, score=0),
    )

    assert result.status == ProofStatus.FAILED
    assert result.independently_verified is False
