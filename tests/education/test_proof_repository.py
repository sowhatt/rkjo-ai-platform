from uuid import uuid4

import pytest

from rkjo_education.intelligence import (
    InMemoryProofChallengeRepository,
    ProofStatus,
    StoredProofChallenge,
)


def make_challenge():
    return StoredProofChallenge(
        tenant_id=uuid4(),
        learner_id=uuid4(),
        course_id=uuid4(),
        competency_code="MATH.FRACTION",
        source_question_id=uuid4(),
        verification_question_id=uuid4(),
    )


def test_stored_challenge_defaults_to_required():
    item = make_challenge()

    assert item.status == ProofStatus.REQUIRED
    assert item.completed_at is None


def test_stored_challenge_requires_competency():
    with pytest.raises(
        ValueError,
        match="competency_code is required",
    ):
        StoredProofChallenge(
            tenant_id=uuid4(),
            learner_id=uuid4(),
            course_id=uuid4(),
            competency_code=" ",
            source_question_id=uuid4(),
            verification_question_id=uuid4(),
        )


def test_stored_challenge_requires_different_question():
    question_id = uuid4()

    with pytest.raises(
        ValueError,
        match="verification question must differ",
    ):
        StoredProofChallenge(
            tenant_id=uuid4(),
            learner_id=uuid4(),
            course_id=uuid4(),
            competency_code="MATH.FRACTION",
            source_question_id=question_id,
            verification_question_id=question_id,
        )


def test_repository_round_trip():
    repository = InMemoryProofChallengeRepository()
    item = make_challenge()

    repository.save(item)

    loaded = repository.get(
        tenant_id=item.tenant_id,
        challenge_id=item.id,
    )

    assert loaded == item


def test_repository_is_tenant_scoped():
    repository = InMemoryProofChallengeRepository()
    item = make_challenge()

    repository.save(item)

    loaded = repository.get(
        tenant_id=uuid4(),
        challenge_id=item.id,
    )

    assert loaded is None
