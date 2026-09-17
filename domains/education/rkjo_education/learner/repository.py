from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .models import LearnerProfile


class LearnerRepository(Protocol):
    def save(self, learner: LearnerProfile) -> LearnerProfile: ...

    def get(self, *, tenant_id: UUID, learner_id: UUID) -> LearnerProfile | None: ...

    def list(self, *, tenant_id: UUID) -> list[LearnerProfile]: ...


class InMemoryLearnerRepository:
    def __init__(self) -> None:
        self._learners: dict[tuple[UUID, UUID], LearnerProfile] = {}

    def save(self, learner: LearnerProfile) -> LearnerProfile:
        self._learners[(learner.tenant_id, learner.id)] = learner
        return learner

    def get(self, *, tenant_id: UUID, learner_id: UUID) -> LearnerProfile | None:
        return self._learners.get((tenant_id, learner_id))

    def list(self, *, tenant_id: UUID) -> list[LearnerProfile]:
        return [
            learner
            for (stored_tenant_id, _), learner in self._learners.items()
            if stored_tenant_id == tenant_id
        ]
