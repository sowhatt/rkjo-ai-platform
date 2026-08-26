"""Course repositories."""

from __future__ import annotations

from typing import Protocol

from rkjo_education.course.models import (
    Course,
)


class CourseRepository(Protocol):
    def save(
        self,
        course: Course,
    ) -> None:
        ...

    def get(
        self,
        *,
        tenant_id: str,
        course_id: str,
    ) -> Course | None:
        ...


class InMemoryCourseRepository:
    def __init__(self) -> None:
        self._items: dict[
            tuple[str, str],
            Course,
        ] = {}

    def save(
        self,
        course: Course,
    ) -> None:
        self._items[
            (
                course.tenant_id,
                course.course_id,
            )
        ] = course

    def get(
        self,
        *,
        tenant_id: str,
        course_id: str,
    ) -> Course | None:
        return self._items.get(
            (
                tenant_id.strip(),
                course_id.strip(),
            )
        )
