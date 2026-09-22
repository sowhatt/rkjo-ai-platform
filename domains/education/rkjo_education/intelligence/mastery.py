from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .autonomy import AutonomyResult


class MasteryLevel(StrEnum):
    NOT_DEMONSTRATED = "not_demonstrated"
    DEVELOPING = "developing"
    PROVISIONAL = "provisional"
    MASTERED = "mastered"


@dataclass(frozen=True, slots=True)
class MasteryObservation:
    correct: bool
    autonomy: AutonomyResult


@dataclass(frozen=True, slots=True)
class MasteryResult:
    level: MasteryLevel
    correct_observations: int
    independent_successes: int
    requires_proof_of_learning: bool


class MasteryCalculator:
    """Deterministic competency mastery from repeated observations."""

    def calculate(
        self,
        observations: list[MasteryObservation],
    ) -> MasteryResult:
        if not observations:
            return MasteryResult(
                level=MasteryLevel.NOT_DEMONSTRATED,
                correct_observations=0,
                independent_successes=0,
                requires_proof_of_learning=False,
            )

        correct = [
            observation
            for observation in observations
            if observation.correct
        ]

        independent = [
            observation
            for observation in correct
            if observation.autonomy.independently_correct
        ]

        assisted_success = any(
            observation.correct
            and observation.autonomy.requires_independent_verification
            for observation in observations
        )

        correct_count = len(correct)
        independent_count = len(independent)

        if independent_count >= 2:
            level = MasteryLevel.MASTERED
            requires_proof = False

        elif independent_count == 1:
            level = MasteryLevel.PROVISIONAL
            requires_proof = True

        elif correct_count > 0:
            level = MasteryLevel.DEVELOPING
            requires_proof = assisted_success

        else:
            level = MasteryLevel.NOT_DEMONSTRATED
            requires_proof = False

        return MasteryResult(
            level=level,
            correct_observations=correct_count,
            independent_successes=independent_count,
            requires_proof_of_learning=requires_proof,
        )
