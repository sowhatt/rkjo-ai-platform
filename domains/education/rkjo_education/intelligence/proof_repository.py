from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID, uuid4

from .proof import ProofStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class StoredProofChallenge:
    tenant_id: UUID
    learner_id: UUID
    course_id: UUID
    competency_code: str
    source_question_id: UUID
    verification_question_id: UUID
    id: UUID = field(default_factory=uuid4)
    status: ProofStatus = ProofStatus.REQUIRED
    created_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        self.competency_code = self.competency_code.strip()

        if not self.competency_code:
            raise ValueError("competency_code is required")

        if self.source_question_id == self.verification_question_id:
            raise ValueError(
                "verification question must differ from source question"
            )


class ProofChallengeRepository(Protocol):
    def save(
        self,
        challenge: StoredProofChallenge,
    ) -> StoredProofChallenge: ...

    def get(
        self,
        *,
        tenant_id: UUID,
        challenge_id: UUID,
    ) -> StoredProofChallenge | None: ...


class InMemoryProofChallengeRepository:
    def __init__(self) -> None:
        self._items: dict[
            tuple[UUID, UUID],
            StoredProofChallenge,
        ] = {}

    def save(
        self,
        challenge: StoredProofChallenge,
    ) -> StoredProofChallenge:
        self._items[(challenge.tenant_id, challenge.id)] = challenge
        return challenge

    def get(
        self,
        *,
        tenant_id: UUID,
        challenge_id: UUID,
    ) -> StoredProofChallenge | None:
        return self._items.get((tenant_id, challenge_id))
