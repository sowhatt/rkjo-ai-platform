from uuid import uuid4

import pytest

from domains.education.rkjo_education.learner.repository import InMemoryLearnerRepository
from domains.education.rkjo_education.learner.service import LearnerNotFoundError, LearnerService
from domains.education.rkjo_education.learning.repository import InMemoryLearningRepository
from domains.education.rkjo_education.learning.service import (
    DuplicateEnrollmentError,
    LearningService,
)


def test_create_and_get_learner_is_tenant_safe() -> None:
    tenant_id = uuid4()
    other_tenant_id = uuid4()
    service = LearnerService(InMemoryLearnerRepository())

    learner = service.create(
        tenant_id=tenant_id,
        first_name="Awa",
        last_name="Mensah",
        level="CE1",
    )

    assert service.get(tenant_id=tenant_id, learner_id=learner.id) == learner
    with pytest.raises(LearnerNotFoundError):
        service.get(tenant_id=other_tenant_id, learner_id=learner.id)


def test_learner_fields_are_normalized() -> None:
    service = LearnerService(InMemoryLearnerRepository())
    learner = service.create(
        tenant_id=uuid4(),
        first_name="  Awa ",
        last_name=" Mensah  ",
        level=" CE1 ",
    )

    assert learner.first_name == "Awa"
    assert learner.last_name == "Mensah"
    assert learner.level == "CE1"


def test_enrollment_rejects_duplicate_for_same_tenant_and_curriculum() -> None:
    service = LearningService(InMemoryLearningRepository())
    tenant_id = uuid4()
    learner_id = uuid4()
    curriculum_id = uuid4()

    service.enroll(
        tenant_id=tenant_id,
        learner_id=learner_id,
        curriculum_id=curriculum_id,
    )

    with pytest.raises(DuplicateEnrollmentError):
        service.enroll(
            tenant_id=tenant_id,
            learner_id=learner_id,
            curriculum_id=curriculum_id,
        )


def test_record_progress_updates_existing_course_progress() -> None:
    repository = InMemoryLearningRepository()
    service = LearningService(repository)
    tenant_id = uuid4()
    learner_id = uuid4()
    course_id = uuid4()

    first = service.record_progress(
        tenant_id=tenant_id,
        learner_id=learner_id,
        course_id=course_id,
        completion_percent=25,
        competency_scores={"MATH.ADD": 60},
    )
    updated = service.record_progress(
        tenant_id=tenant_id,
        learner_id=learner_id,
        course_id=course_id,
        completion_percent=75,
        competency_scores={"MATH.ADD": 85},
    )

    assert updated.id == first.id
    assert updated.completion_percent == 75
    assert updated.competency_scores["MATH.ADD"] == 85


@pytest.mark.parametrize("value", [-1, 101])
def test_progress_rejects_invalid_percentages(value: int) -> None:
    service = LearningService(InMemoryLearningRepository())

    with pytest.raises(ValueError):
        service.record_progress(
            tenant_id=uuid4(),
            learner_id=uuid4(),
            course_id=uuid4(),
            completion_percent=value,
        )


def test_competencies_are_tenant_scoped() -> None:
    repository = InMemoryLearningRepository()
    service = LearningService(repository)
    tenant_id = uuid4()
    other_tenant_id = uuid4()

    competency = service.create_competency(
        tenant_id=tenant_id,
        code="MATH.ADD",
        label="Additionner des nombres entiers",
    )

    assert repository.list_competencies(tenant_id=tenant_id) == [competency]
    assert repository.list_competencies(tenant_id=other_tenant_id) == []
