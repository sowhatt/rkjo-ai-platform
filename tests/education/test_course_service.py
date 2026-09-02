import pytest

from rkjo_education.course.models import Course
from rkjo_education.course.repository import (
    InMemoryCourseRepository,
)
from rkjo_education.course.service import CourseService


def build_course(
    tenant_id: str = "demo-tenant",
) -> Course:
    return Course(
        course_id="medicine-anatomy-001",
        tenant_id=tenant_id,
        title="Anatomie du coeur",
        subject="Anatomie",
        level="Médecine",
        curriculum_id="medicine-demo",
    )


def test_create_and_get_course():
    repository = InMemoryCourseRepository()
    service = CourseService(repository)

    created = service.create(build_course())

    assert created.course_id == (
        "medicine-anatomy-001"
    )
    assert created.tenant_id == "demo-tenant"

    loaded = service.get(
        tenant_id="demo-tenant",
        course_id="medicine-anatomy-001",
    )

    assert loaded == created


def test_course_is_tenant_safe():
    repository = InMemoryCourseRepository()
    service = CourseService(repository)

    service.create(build_course())

    with pytest.raises(LookupError):
        service.get(
            tenant_id="other-tenant",
            course_id="medicine-anatomy-001",
        )


def test_attach_document_is_idempotent():
    repository = InMemoryCourseRepository()
    service = CourseService(repository)

    service.create(build_course())

    service.attach_document(
        tenant_id="demo-tenant",
        course_id="medicine-anatomy-001",
        document_id="demo-anatomie-coeur",
    )

    updated = service.attach_document(
        tenant_id="demo-tenant",
        course_id="medicine-anatomy-001",
        document_id="demo-anatomie-coeur",
    )

    assert updated.document_ids == [
        "demo-anatomie-coeur"
    ]


def test_list_courses_is_tenant_safe():
    repository = InMemoryCourseRepository()
    service = CourseService(repository)

    service.create(
        Course(
            course_id="course-a",
            tenant_id="tenant-a",
            title="Anatomie",
            subject="Anatomie",
            level="Médecine",
        )
    )

    service.create(
        Course(
            course_id="course-b",
            tenant_id="tenant-a",
            title="Physiologie",
            subject="Physiologie",
            level="Médecine",
        )
    )

    service.create(
        Course(
            course_id="course-c",
            tenant_id="tenant-b",
            title="SVT",
            subject="SVT",
            level="Terminale",
        )
    )

    courses = service.list_courses(
        tenant_id="tenant-a"
    )

    assert {
        course.course_id
        for course in courses
    } == {
        "course-a",
        "course-b",
    }
