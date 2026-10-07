from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import exp

from rkjo_education.events import EducationEventType, EducationLearningEvent

from .mastery import LearnerObservation


@dataclass(frozen=True, slots=True)
class HistoricalCompetencyState:
    competency_code: str
    mastery: float
    autonomy: float
    retention: float
    successful_proof: bool
    latest_correct: bool | None
    latest_observation_failed: bool
    has_observation: bool
    latest_help: float
    consecutive_failures: int
    consecutive_no_hint_successes: int
    distinct_success_exercises: int


class LearnerModelProjector:
    """Project CDC v2.3 learner signals from the durable learning event stream."""

    @staticmethod
    def _help_from_autonomy(score: int | float) -> float:
        value = float(score)
        if value > 1:
            value /= 100.0
        return 1.0 - max(0.0, min(1.0, value))

    @staticmethod
    def _attempt_score(*, correct: bool, help_level: float) -> float:
        if not correct:
            return 0.0
        if help_level <= 0:
            return 0.7
        if help_level <= 0.25:
            return 0.5
        if help_level < 1.0:
            return 0.3
        return 0.1

    def project(
        self,
        events: list[EducationLearningEvent],
        *,
        competency_code: str,
        now: datetime | None = None,
        prior: float = .30,
    ) -> HistoricalCompetencyState:
        now = now or datetime.now(timezone.utc)
        relevant = [e for e in events if e.competency_code == competency_code]
        observations: list[LearnerObservation] = []
        help_levels: list[float] = []
        answer_events: list[EducationLearningEvent] = []
        successful_proof = False
        last_success_at: datetime | None = None
        latest_help = 0.0

        autonomy_by_question: dict[object, float] = {}
        for event in relevant:
            if event.event_type == EducationEventType.AUTONOMY_UPDATED:
                score = event.payload.get("autonomy_score")
                if isinstance(score, (int, float)):
                    help_level = self._help_from_autonomy(score)
                    autonomy_by_question[event.question_id] = help_level
                    help_levels.append(help_level)
                    latest_help = help_level
            elif event.event_type == EducationEventType.ANSWER_SUBMITTED:
                answer_events.append(event)
                correct = event.payload.get("correct") is True
                help_level = autonomy_by_question.get(event.question_id, 0.0)
                score = self._attempt_score(correct=correct, help_level=help_level)
                observations.append(LearnerObservation(score=score, weight=1.0))
                if correct and help_level == 0:
                    last_success_at = event.occurred_at
            elif event.event_type == EducationEventType.CORRECTED_COPY_OBSERVED:
                score = event.payload.get("score")
                weight = event.payload.get("weight", 0.8)
                if isinstance(score, (int, float)) and isinstance(weight, (int, float)):
                    observations.append(
                        LearnerObservation(
                            score=max(0.0, min(1.0, float(score))),
                            weight=max(0.0, float(weight)),
                        )
                    )
                    if float(score) > 0:
                        last_success_at = event.occurred_at
            elif event.event_type == EducationEventType.PROOF_PASSED:
                successful_proof = True
                observations.append(LearnerObservation(score=1.0, weight=1.0))
                last_success_at = event.occurred_at
            elif event.event_type == EducationEventType.PROOF_FAILED:
                successful_proof = False
                observations.append(LearnerObservation(score=0.0, weight=1.0))

        # Events are emitted answer then autonomy in the current API. Reconcile
        # answer observations with the explicit autonomy event when available.
        if answer_events:
            observations = []
            last_success_at = None
            for event in answer_events:
                help_level = autonomy_by_question.get(event.question_id, 0.0)
                correct = event.payload.get("correct") is True
                score = self._attempt_score(correct=correct, help_level=help_level)
                observations.append(LearnerObservation(score=score, weight=1.0))
                if correct and help_level == 0:
                    if last_success_at is None or event.occurred_at > last_success_at:
                        last_success_at = event.occurred_at
            for event in relevant:
                if event.event_type == EducationEventType.PROOF_PASSED:
                    observations.append(LearnerObservation(score=1.0, weight=1.0))
                    if last_success_at is None or event.occurred_at > last_success_at:
                        last_success_at = event.occurred_at
                elif event.event_type == EducationEventType.PROOF_FAILED:
                    observations.append(LearnerObservation(score=0.0, weight=1.0))
                elif event.event_type == EducationEventType.CORRECTED_COPY_OBSERVED:
                    score = event.payload.get("score")
                    weight = event.payload.get("weight", 0.8)
                    if isinstance(score, (int, float)) and isinstance(weight, (int, float)):
                        observations.append(
                            LearnerObservation(
                                score=max(0.0, min(1.0, float(score))),
                                weight=max(0.0, float(weight)),
                            )
                        )
                        if float(score) > 0 and (last_success_at is None or event.occurred_at > last_success_at):
                            last_success_at = event.occurred_at

        recent = observations[-10:]
        numerator = prior
        denominator = 1.0
        for rank, observation in enumerate(reversed(recent)):
            decay = .85 ** rank
            numerator += observation.weight * decay * observation.score
            denominator += observation.weight * decay
        mastery = numerator / denominator
        if not successful_proof:
            mastery = min(mastery, .75)

        recent_help = help_levels[-5:]
        autonomy = (
            sum(1.0 - h for h in recent_help) / len(recent_help)
            if recent_help else 0.0
        )
        # CDC v2.3 retention stability S(c): start at 2 days, grow after
        # spaced no-help success, shrink after failure.
        stability_days = 2.0
        retention_anchor: datetime | None = None
        for event in sorted(relevant, key=lambda item: item.occurred_at):
            successful_anchor = False
            failed_observation = False
            if event.event_type == EducationEventType.ANSWER_SUBMITTED:
                correct = event.payload.get("correct") is True
                help_level = autonomy_by_question.get(event.question_id, 0.0)
                successful_anchor = correct and help_level == 0
                failed_observation = not correct
            elif event.event_type == EducationEventType.CORRECTED_COPY_OBSERVED:
                score = event.payload.get("score")
                # The CDC defines successful corrected copies as retention
                # anchors but gives no partial-score threshold. Only an
                # unambiguous full success is treated as successful here.
                successful_anchor = isinstance(score, (int, float)) and float(score) >= 1.0
                failed_observation = score == 0
            elif event.event_type == EducationEventType.PROOF_PASSED:
                successful_anchor = True
            elif event.event_type == EducationEventType.PROOF_FAILED:
                failed_observation = True

            if successful_anchor:
                if (
                    retention_anchor is not None
                    and (event.occurred_at - retention_anchor).total_seconds() >= 86400
                ):
                    stability_days *= 2.5
                retention_anchor = event.occurred_at
            elif failed_observation:
                stability_days = max(1.0, stability_days * 0.5)

        if retention_anchor is not None:
            last_success_at = retention_anchor
        days = (
            max(0.0, (now - last_success_at).total_seconds() / 86400)
            if last_success_at else 9999.0
        )
        retention = exp(-days / stability_days) if last_success_at else 0.0

        failures = 0
        successes = 0
        distinct: set[object] = set()
        latest_correct = None
        latest_observation_failed = False
        latest_significant = next((event for event in reversed(relevant) if event.event_type in {EducationEventType.ANSWER_SUBMITTED, EducationEventType.CORRECTED_COPY_OBSERVED, EducationEventType.PROOF_PASSED, EducationEventType.PROOF_FAILED}), None)
        if latest_significant is not None:
            if latest_significant.event_type == EducationEventType.ANSWER_SUBMITTED:
                latest_observation_failed = latest_significant.payload.get("correct") is False
            elif latest_significant.event_type == EducationEventType.CORRECTED_COPY_OBSERVED:
                latest_observation_failed = latest_significant.payload.get("score") == 0
            elif latest_significant.event_type == EducationEventType.PROOF_FAILED:
                latest_observation_failed = True
        for event in reversed(answer_events):
            correct = event.payload.get("correct") is True
            if latest_correct is None:
                latest_correct = correct
            if correct:
                break
            failures += 1
        for event in reversed(answer_events):
            if event.payload.get("correct") is not True:
                break
            if autonomy_by_question.get(event.question_id, 0.0) != 0:
                break
            successes += 1
            distinct.add(event.question_id)

        return HistoricalCompetencyState(
            competency_code=competency_code,
            mastery=max(0.0, min(1.0, mastery)),
            autonomy=max(0.0, min(1.0, autonomy)),
            retention=max(0.0, min(1.0, retention)),
            successful_proof=successful_proof,
            latest_correct=latest_correct,
            latest_observation_failed=latest_observation_failed,
            has_observation=bool(observations),
            latest_help=latest_help,
            consecutive_failures=failures,
            consecutive_no_hint_successes=successes,
            distinct_success_exercises=len(distinct),
        )
