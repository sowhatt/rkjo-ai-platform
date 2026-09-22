import os
from uuid import uuid4

import pytest

from rkjo_education.intelligence import (
    ProofStatus,
    StoredProofChallenge,
)
from rkjo_education.intelligence.proof_postgres_repository import (
    PostgresProofChallengeRepository,
)


DATABASE_URL = os.getenv("RKJO_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="RKJO_DATABASE_URL is not configured",
)


def test_postgres_proof_challenge_round_trip():
    repository = PostgresProofChallengeRepository(DATABASE_URL)

    item = StoredProofChallenge(
        tenant_id=uuid4(),
        learner_id=uuid4(),
        course_id=uuid4(),
        competency_code="MATH.FRACTION",
        source_question_id=uuid4(),
        verification_question_id=uuid4(),
    )

    repository.save(item)

    loaded = repository.get(
        tenant_id=item.tenant_id,
        challenge_id=item.id,
    )

    assert loaded is not None
    assert loaded.id == item.id
    assert loaded.learner_id == item.learner_id
    assert loaded.course_id == item.course_id
    assert loaded.competency_code == "MATH.FRACTION"
    assert loaded.source_question_id == item.source_question_id
    assert (
        loaded.verification_question_id
        == item.verification_question_id
    )
    assert loaded.status == ProofStatus.REQUIRED
    assert loaded.completed_at is None
