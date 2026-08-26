"""Curriculum repositories."""

from __future__ import annotations

from typing import Protocol

from rkjo_education.curriculum.models import (
    Curriculum,
)


class CurriculumRepository(Protocol):
    def save(
        self,
        curriculum: Curriculum,
    ) -> None:
        ...

    def get(
        self,
        *,
        tenant_id: str,
        curriculum_id: str,
    ) -> Curriculum | None:
        ...


class InMemoryCurriculumRepository:
    def __init__(self) -> None:
        self._items: dict[
            tuple[str, str],
            Curriculum,
        ] = {}

    def save(
        self,
        curriculum: Curriculum,
    ) -> None:
        self._items[
            (
                curriculum.tenant_id,
                curriculum.curriculum_id,
            )
        ] = curriculum

    def get(
        self,
        *,
        tenant_id: str,
        curriculum_id: str,
    ) -> Curriculum | None:
        return self._items.get(
            (
                tenant_id.strip(),
                curriculum_id.strip(),
            )
        )
