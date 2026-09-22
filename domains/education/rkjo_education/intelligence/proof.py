from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from .autonomy import AutonomyResult
from .mastery import MasteryLevel, MasteryResult


class ProofStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    REQUIRED = "required"
    PASSED = "passed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ProofChallenge:
    competency_code: str
    source_question_id: UUID
    verification_question_id: UUID

    def __post_init__(self) -> None:
        code = self.competency_code.strip()
        if not code:
            raise ValueError("competency_code is required")
        if self.source_question_id == self.verification_question_id:
            raise ValueError(
                "verification question must differ from source question"
            )
        object.__setattr__(self, "competency_code", code)


@dataclass(frozen=True, slots=True)
class ProofResult:
    status: ProofStatus
    competency_code: str
    independently_verified: bool


class ProofOfLearningService:
    """Deterministic verification of independent learning evidence."""

    def required(self, mastery: MasteryResult) -> bool:
        return (
            mastery.requires_proof_of_learning
            and mastery.level is not MasteryLevel.MASTERED
        )

    def evaluate(
        self,
        *,
        challenge: ProofChallenge,
        verification_competency_code: str,
        correct: bool,
        autonomy: AutonomyResult,
    ) -> ProofResult:
        verification_code = verification_competency_code.strip()

        if not verification_code:
            raise ValueError("verification competency_code is required")

        if verification_code != challenge.competency_code:
            raise ValueError(
                "verification question must test the same competency"
            )

        passed = correct and autonomy.independently_correct

        return ProofResult(
            status=ProofStatus.PASSED if passed else ProofStatus.FAILED,
            competency_code=challenge.competency_code,
            independently_verified=passed,
        )
