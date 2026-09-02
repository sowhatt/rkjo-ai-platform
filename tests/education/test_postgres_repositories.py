import os
import uuid

import psycopg
import pytest

from rkjo_education.course.models import Course
from rkjo_education.course.postgres_repository import (
    PostgresCourseRepository,
)
from rkjo_education.curriculum.models import (
    Curriculum,
    CurriculumConcept,
    CurriculumTopic,
)
from rkjo_education.curriculum.postgres_repository import (
    PostgresCurriculumRepository,
)


DATABASE_URL = os.getenv(
    "RKJO_DATABASE_URL",
    "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
)


@pytest.fixture()
def database_url():
    try:
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute("SELECT 1")
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL is unavailable.")

    return DATABASE_URL


def test_curriculum_survives_repository_recreation(
    database_url,
):
    suffix = uuid.uuid4().hex[:8]

    curriculum = Curriculum(
        curriculum_id=f"curriculum-{suffix}",
        tenant_id="education-test",
        country="BJ",
        level="Terminale",
        subject="SVT",
        academic_year="2026-2027",
        topics=[
            CurriculumTopic(
                topic_id="genetique",
                title="Génétique",
                concepts=[
                    CurriculumConcept(
                        concept_id="adn",
                        title="ADN",
                    ),
                ],
            ),
        ],
    )

    repository = PostgresCurriculumRepository(
        database_url
    )
    repository.save(curriculum)

    recreated = PostgresCurriculumRepository(
        database_url
    )

    loaded = recreated.get(
        tenant_id="education-test",
        curriculum_id=curriculum.curriculum_id,
    )

    assert loaded == curriculum


def test_course_survives_repository_recreation(
    database_url,
):
    suffix = uuid.uuid4().hex[:8]

    course = Course(
        course_id=f"course-{suffix}",
        tenant_id="education-test",
        title="Anatomie du coeur",
        subject="Anatomie",
        level="Médecine",
        curriculum_id="medicine-demo",
        document_ids=[
            "demo-anatomie-coeur",
        ],
    )

    repository = PostgresCourseRepository(
        database_url
    )
    repository.save(course)

    recreated = PostgresCourseRepository(
        database_url
    )

    loaded = recreated.get(
        tenant_id="education-test",
        course_id=course.course_id,
    )

    assert loaded == course


def test_postgres_course_is_tenant_safe(
    database_url,
):
    suffix = uuid.uuid4().hex[:8]

    course = Course(
        course_id=f"tenant-course-{suffix}",
        tenant_id="tenant-a",
        title="SVT",
        subject="SVT",
        level="Terminale",
    )

    repository = PostgresCourseRepository(
        database_url
    )
    repository.save(course)

    assert (
        repository.get(
            tenant_id="tenant-b",
            course_id=course.course_id,
        )
        is None
    )


def test_postgres_course_list_is_tenant_safe(
    database_url,
):
    suffix = uuid.uuid4().hex[:8]

    repository = PostgresCourseRepository(
        database_url
    )

    repository.save(
        Course(
            course_id=f"a-{suffix}",
            tenant_id=f"tenant-a-{suffix}",
            title="Anatomie",
            subject="Anatomie",
            level="Médecine",
        )
    )

    repository.save(
        Course(
            course_id=f"b-{suffix}",
            tenant_id=f"tenant-a-{suffix}",
            title="Physiologie",
            subject="Physiologie",
            level="Médecine",
        )
    )

    repository.save(
        Course(
            course_id=f"c-{suffix}",
            tenant_id=f"tenant-b-{suffix}",
            title="SVT",
            subject="SVT",
            level="Terminale",
        )
    )

    courses = repository.list_for_tenant(
        f"tenant-a-{suffix}"
    )

    assert {
        course.course_id
        for course in courses
    } == {
        f"a-{suffix}",
        f"b-{suffix}",
    }
