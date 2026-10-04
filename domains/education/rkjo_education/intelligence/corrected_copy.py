from __future__ import annotations

from dataclasses import dataclass

from .mastery import LearnerObservation


@dataclass(frozen=True, slots=True)
class CorrectedQuestionEvidence:
    competency_code: str
    earned_points: float
    max_points: float
    alignment_confidence: float

    def __post_init__(self) -> None:
        if not self.competency_code.strip():
            raise ValueError("competency_code is required")
        if self.max_points <= 0:
            raise ValueError("max_points must be greater than zero")
        if not 0 <= self.earned_points <= self.max_points:
            raise ValueError("earned_points must be between zero and max_points")
        if not 0 <= self.alignment_confidence <= 1:
            raise ValueError("alignment_confidence must be between zero and one")

    @property
    def requires_confirmation(self) -> bool:
        return self.alignment_confidence < 0.70

    def to_mastery_observation(self, *, confirmed: bool = False) -> LearnerObservation | None:
        if self.requires_confirmation and not confirmed:
            return None
        return LearnerObservation(score=self.earned_points / self.max_points, weight=0.8)


class CorrectedCopyEvidenceService:
    """Corrected copies affect Mastery/Retention evidence, never Autonomy."""

    @staticmethod
    def observations(
        questions: list[CorrectedQuestionEvidence],
        *,
        confirmed_competencies: set[str] | None = None,
    ) -> dict[str, list[LearnerObservation]]:
        confirmed = confirmed_competencies or set()
        result: dict[str, list[LearnerObservation]] = {}
        for question in questions:
            observation = question.to_mastery_observation(
                confirmed=question.competency_code in confirmed,
            )
            if observation is not None:
                result.setdefault(question.competency_code, []).append(observation)
        return result
