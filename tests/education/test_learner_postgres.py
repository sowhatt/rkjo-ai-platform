from uuid import uuid4

import os

from rkjo_education.learner.postgres_repository import PostgresLearnerRepository
from rkjo_education.learner.service import LearnerService
from rkjo_education.learning.postgres_repository import PostgresLearningRepository
from rkjo_education.learning.service import LearningService


def database_url() -> str:
    return os.environ["RKJO_DATABASE_URL"]


def test_postgres_learner_roundtrip():
    tenant_id = uuid4()
    service = LearnerService(PostgresLearnerRepository(database_url()))

    learner = service.create(
        tenant_id=tenant_id,
        first_name="Awa",
        last_name="Mensah",
        level="CE1",
    )

    restored = service.get(tenant_id=tenant_id, learner_id=learner.id)

    assert restored.id == learner.id
    assert restored.first_name == "Awa"
    assert restored.last_name == "Mensah"


def test_postgres_learning_roundtrip():
    tenant_id = uuid4()
    learner_id = uuid4()
    curriculum_id = uuid4()
    course_id = uuid4()
    service = LearningService(PostgresLearningRepository(database_url()))

    enrollment = service.enroll(
        tenant_id=tenant_id,
        learner_id=learner_id,
        curriculum_id=curriculum_id,
    )
    competency = service.create_competency(
        tenant_id=tenant_id,
        code="MATH.ADD",
        label="Additionner",
    )
    progress = service.record_progress(
        tenant_id=tenant_id,
        learner_id=learner_id,
        course_id=course_id,
        completion_percent=75,
        competency_scores={competency.code: 88},
    )

    restored_enrollment = service.repository.find_enrollment(
        tenant_id=tenant_id,
        learner_id=learner_id,
        curriculum_id=curriculum_id,
    )
    restored_progress = service.repository.find_progress(
        tenant_id=tenant_id,
        learner_id=learner_id,
        course_id=course_id,
    )

    assert restored_enrollment.id == enrollment.id
    assert restored_progress.id == progress.id
    assert restored_progress.completion_percent == 75
    assert restored_progress.competency_scores["MATH.ADD"] == 88
