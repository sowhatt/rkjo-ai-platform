from __future__ import annotations

from uuid import UUID

from .models import LearnerProfile
from .repository import LearnerRepository


class LearnerNotFoundError(LookupError):
    pass


class LearnerService:
    def __init__(self, repository: LearnerRepository) -> None:
        self._repository = repository

    def create(
        self,
        *,
        tenant_id: UUID,
        first_name: str,
        last_name: str,
        level: str,
    ) -> LearnerProfile:
        first_name = first_name.strip()
        last_name = last_name.strip()
        level = level.strip()
        if not first_name or not last_name or not level:
            raise ValueError("first_name, last_name and level are required")

        learner = LearnerProfile(
            tenant_id=tenant_id,
            first_name=first_name,
            last_name=last_name,
            level=level,
        )
        return self._repository.save(learner)

    def get(self, *, tenant_id: UUID, learner_id: UUID) -> LearnerProfile:
        learner = self._repository.get(tenant_id=tenant_id, learner_id=learner_id)
        if learner is None:
            raise LearnerNotFoundError(str(learner_id))
        return learner

    def list(self, *, tenant_id: UUID) -> list[LearnerProfile]:
        return self._repository.list(tenant_id=tenant_id)
