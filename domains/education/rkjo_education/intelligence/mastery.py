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



@dataclass(frozen=True, slots=True)
class LearnerObservation:
    score: float
    weight: float
    rank: int = 0


@dataclass(frozen=True, slots=True)
class LearnerModelState:
    mastery: float
    autonomy: float
    retention: float
    status: str
    review_due: bool


class LearnerModelCalculator:
    """CDC v2.3 deterministic Mastery / Autonomy / Retention formulas."""

    DECAY = 0.85
    PRIOR_WEIGHT = 1.0
    DEFAULT_PRIOR = 0.30

    def mastery(
        self,
        observations: list[LearnerObservation],
        *,
        prior: float | None = None,
        successful_proof: bool = False,
    ) -> float:
        recent = observations[-10:]
        numerator = self.PRIOR_WEIGHT * (
            self.DEFAULT_PRIOR if prior is None else prior
        )
        denominator = self.PRIOR_WEIGHT
        for rank, observation in enumerate(reversed(recent)):
            decay = self.DECAY ** rank
            numerator += observation.weight * decay * observation.score
            denominator += observation.weight * decay
        value = numerator / denominator
        if not successful_proof:
            value = min(value, 0.75)
        return max(0.0, min(1.0, value))

    @staticmethod
    def autonomy(help_levels: list[float]) -> float:
        recent = help_levels[-5:]
        if not recent:
            return 0.0
        return sum(1.0 - max(0.0, min(1.0, level)) for level in recent) / len(recent)

    @staticmethod
    def retention(*, days_since_success: float, stability_days: float) -> float:
        from math import exp
        stability = max(1.0, stability_days)
        return max(0.0, min(1.0, exp(-max(0.0, days_since_success) / stability)))

    @staticmethod
    def next_stability(
        *,
        current_stability_days: float,
        successful_no_help: bool,
        spaced_at_least_one_day: bool = False,
        failed: bool = False,
    ) -> float:
        stability = max(1.0, current_stability_days)
        if failed:
            return max(1.0, stability * 0.5)
        if successful_no_help and spaced_at_least_one_day:
            return stability * 2.5
        return stability

    def calculate(
        self,
        *,
        observations: list[LearnerObservation],
        help_levels: list[float],
        days_since_success: float,
        stability_days: float = 2.0,
        prior: float | None = None,
        successful_proof: bool = False,
    ) -> LearnerModelState:
        mastery = self.mastery(
            observations,
            prior=prior,
            successful_proof=successful_proof,
        )
        autonomy = self.autonomy(help_levels)
        retention = self.retention(
            days_since_success=days_since_success,
            stability_days=stability_days,
        )
        if not observations:
            status = "unevaluated"
        elif mastery < 0.40:
            status = "non-mastered"
        elif mastery < 0.75 or not successful_proof:
            status = "fragile"
        else:
            status = "acquired"
        return LearnerModelState(
            mastery=mastery,
            autonomy=autonomy,
            retention=retention,
            status=status,
            review_due=retention < 0.60,
        )
