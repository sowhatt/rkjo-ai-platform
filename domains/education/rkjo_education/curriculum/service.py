"""Curriculum application service."""

from __future__ import annotations

from rkjo_education.curriculum.models import (
    Curriculum,
)
from rkjo_education.curriculum.repository import (
    CurriculumRepository,
)


class CurriculumService:
    def __init__(
        self,
        repository: CurriculumRepository,
    ) -> None:
        self.repository = repository

    def create(
        self,
        curriculum: Curriculum,
    ) -> Curriculum:
        existing = self.repository.get(
            tenant_id=curriculum.tenant_id,
            curriculum_id=(
                curriculum.curriculum_id
            ),
        )

        if existing is not None:
            raise ValueError(
                "Curriculum already exists."
            )

        self.repository.save(
            curriculum
        )

        return curriculum

    def get(
        self,
        *,
        tenant_id: str,
        curriculum_id: str,
    ) -> Curriculum:
        normalized_tenant_id = (
            tenant_id.strip()
        )
        normalized_curriculum_id = (
            curriculum_id.strip()
        )

        if not normalized_tenant_id:
            raise ValueError(
                "tenant_id must not be empty."
            )

        if not normalized_curriculum_id:
            raise ValueError(
                "curriculum_id must not be empty."
            )

        curriculum = self.repository.get(
            tenant_id=normalized_tenant_id,
            curriculum_id=(
                normalized_curriculum_id
            ),
        )

        if curriculum is None:
            raise LookupError(
                "Curriculum not found."
            )

        return curriculum
