"""Course application service."""

from __future__ import annotations

from dataclasses import replace

from rkjo_education.course.models import (
    Course,
)
from rkjo_education.course.repository import (
    CourseRepository,
)


class CourseService:
    def __init__(
        self,
        repository: CourseRepository,
    ) -> None:
        self.repository = repository

    def create(
        self,
        course: Course,
    ) -> Course:
        existing = self.repository.get(
            tenant_id=course.tenant_id,
            course_id=course.course_id,
        )

        if existing is not None:
            raise ValueError(
                "Course already exists."
            )

        self.repository.save(
            course
        )

        return course

    def get(
        self,
        *,
        tenant_id: str,
        course_id: str,
    ) -> Course:
        normalized_tenant_id = (
            tenant_id.strip()
        )
        normalized_course_id = (
            course_id.strip()
        )

        if not normalized_tenant_id:
            raise ValueError(
                "tenant_id must not be empty."
            )

        if not normalized_course_id:
            raise ValueError(
                "course_id must not be empty."
            )

        course = self.repository.get(
            tenant_id=normalized_tenant_id,
            course_id=normalized_course_id,
        )

        if course is None:
            raise LookupError(
                "Course not found."
            )

        return course

    def list_courses(
        self,
        *,
        tenant_id: str,
    ) -> list[Course]:
        normalized_tenant_id = (
            tenant_id.strip()
        )

        if not normalized_tenant_id:
            raise ValueError(
                "tenant_id must not be empty."
            )

        return self.repository.list_for_tenant(
            normalized_tenant_id
        )

    def attach_document(
        self,
        *,
        tenant_id: str,
        course_id: str,
        document_id: str,
    ) -> Course:
        course = self.get(
            tenant_id=tenant_id,
            course_id=course_id,
        )

        normalized_document_id = (
            document_id.strip()
        )

        if not normalized_document_id:
            raise ValueError(
                "document_id must not be empty."
            )

        if (
            normalized_document_id
            in course.document_ids
        ):
            return course

        updated = replace(
            course,
            document_ids=[
                *course.document_ids,
                normalized_document_id,
            ],
        )

        self.repository.save(
            updated
        )

        return updated
