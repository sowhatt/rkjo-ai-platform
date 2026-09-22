from __future__ import annotations

from dataclasses import dataclass

from rkjo_education.assessment.models import AttemptAnswerEvidence
from rkjo_education.policy import AssistanceLevel


@dataclass(frozen=True, slots=True)
class AutonomyEvidence:
    correct: bool
    assistance_level: AssistanceLevel
    hints_used: int
    attempt_count: int
    response_time_seconds: int | None = None


@dataclass(frozen=True, slots=True)
class AutonomyResult:
    score: int
    independently_correct: bool
    requires_independent_verification: bool


class AutonomyCalculator:
    """Deterministic autonomy scoring from observable learning evidence."""

    _BASE_SCORES = {
        AssistanceLevel.NONE: 100,
        AssistanceLevel.SOCRATIC_QUESTION: 90,
        AssistanceLevel.LIGHT_HINT: 75,
        AssistanceLevel.STRONG_HINT: 55,
        AssistanceLevel.GUIDED_METHOD: 30,
        AssistanceLevel.EXPLAINED_SOLUTION: 0,
    }

    def calculate(self, evidence: AutonomyEvidence) -> AutonomyResult:
        if not evidence.correct:
            return AutonomyResult(
                score=0,
                independently_correct=False,
                requires_independent_verification=False,
            )

        base_score = self._BASE_SCORES[evidence.assistance_level]

        extra_attempts = max(0, evidence.attempt_count - 1)
        penalty = (extra_attempts * 5) + (evidence.hints_used * 5)

        score = max(0, min(100, base_score - penalty))

        independently_correct = (
            evidence.assistance_level is AssistanceLevel.NONE
            and evidence.hints_used == 0
            and evidence.attempt_count == 1
        )

        requires_independent_verification = (
            evidence.assistance_level >= AssistanceLevel.STRONG_HINT
        )

        return AutonomyResult(
            score=score,
            independently_correct=independently_correct,
            requires_independent_verification=requires_independent_verification,
        )

    def from_attempt_evidence(
        self,
        *,
        correct: bool,
        evidence: AttemptAnswerEvidence | None,
    ) -> AutonomyResult:
        if evidence is None:
            return AutonomyResult(
                score=0,
                independently_correct=False,
                requires_independent_verification=True,
            )

        return self.calculate(
            AutonomyEvidence(
                correct=correct,
                assistance_level=evidence.assistance_level,
                hints_used=evidence.hints_used,
                attempt_count=evidence.attempt_count,
                response_time_seconds=evidence.response_time_seconds,
            )
        )
