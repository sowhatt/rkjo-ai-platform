from uuid import uuid4

from rkjo_education.learner.repository import InMemoryLearnerRepository
from rkjo_education.learner.service import LearnerService
from rkjo_education.learning.repository import InMemoryLearningRepository
from rkjo_education.learning.service import LearningService


def test_learner_curriculum_course_progress_journey() -> None:
    tenant_id = uuid4()
    curriculum_id = uuid4()
    course_id = uuid4()

    learner_service = LearnerService(InMemoryLearnerRepository())
    learning_service = LearningService(InMemoryLearningRepository())

    learner = learner_service.create(
        tenant_id=tenant_id,
        first_name="Awa",
        last_name="Mensah",
        level="CE1",
    )
    enrollment = learning_service.enroll(
        tenant_id=tenant_id,
        learner_id=learner.id,
        curriculum_id=curriculum_id,
    )
    competency = learning_service.create_competency(
        tenant_id=tenant_id,
        code="MATH.ADD",
        label="Additionner des nombres entiers",
    )
    progress = learning_service.record_progress(
        tenant_id=tenant_id,
        learner_id=learner.id,
        course_id=course_id,
        completion_percent=100,
        competency_scores={competency.code: 90},
    )

    assert enrollment.learner_id == learner.id
    assert enrollment.curriculum_id == curriculum_id
    assert progress.completion_percent == 100
    assert progress.competency_scores[competency.code] == 90
