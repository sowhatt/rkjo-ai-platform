from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from rkjo_education.events import EducationEventType, EducationLearningEvent

from .models import LearnerSupervisionState


class LearnerSupervisionProjection:
    """Idempotent in-memory projection for the live learner supervision view."""

    def __init__(self) -> None:
        self._states: dict[tuple[UUID, UUID], LearnerSupervisionState] = {}
        self._processed_event_ids: set[UUID] = set()

    def apply(self, event: EducationLearningEvent) -> LearnerSupervisionState:
        key = (event.tenant_id, event.learner_id)
        current = self._states.get(key)
        if current is None:
            current = LearnerSupervisionState(
                tenant_id=event.tenant_id,
                learner_id=event.learner_id,
            )

        if event.event_id in self._processed_event_ids:
            return current.model_copy(deep=True)

        updates = {
            "course_id": event.course_id or current.course_id,
            "session_id": event.session_id or current.session_id,
            "assessment_id": event.assessment_id or current.assessment_id,
            "last_event_at": event.occurred_at,
            "last_event_id": event.event_id,
        }

        if event.event_type in (
            EducationEventType.SESSION_STARTED,
            EducationEventType.ASSESSMENT_STARTED,
        ):
            updates["active"] = True
        elif event.event_type == EducationEventType.SESSION_COMPLETED:
            updates["active"] = False
        elif event.event_type == EducationEventType.ANSWER_SUBMITTED:
            updates["answers_submitted"] = current.answers_submitted + 1
        elif event.event_type == EducationEventType.HINT_REQUESTED:
            updates["hints_requested"] = current.hints_requested + 1
        elif event.event_type == EducationEventType.TUTOR_REQUESTED:
            updates["tutor_requests"] = current.tutor_requests + 1
        elif event.event_type == EducationEventType.AUTONOMY_UPDATED:
            score = event.payload.get("autonomy_score")
            if isinstance(score, int) and not isinstance(score, bool) and 0 <= score <= 100:
                updates["autonomy_score"] = score
        elif event.event_type == EducationEventType.MASTERY_UPDATED:
            mastery = event.payload.get("mastery")
            if isinstance(mastery, str) and mastery.strip():
                updates["mastery"] = mastery.strip()
        elif event.event_type == EducationEventType.PROOF_REQUESTED:
            updates["proof_status"] = "requested"
        elif event.event_type == EducationEventType.PROOF_PASSED:
            updates["proof_status"] = "passed"
        elif event.event_type == EducationEventType.PROOF_FAILED:
            updates["proof_status"] = "failed"

        next_state = current.model_copy(update=updates)
        self._states[key] = next_state
        self._processed_event_ids.add(event.event_id)
        return next_state.model_copy(deep=True)

    def replay(
        self,
        events: Iterable[EducationLearningEvent],
        *,
        tenant_id: UUID,
        learner_id: UUID,
    ) -> LearnerSupervisionState | None:
        """Rebuild one learner from a clean projection state."""
        key = (tenant_id, learner_id)
        self._states.pop(key, None)

        ordered_events = sorted(
            (
                event
                for event in events
                if event.tenant_id == tenant_id and event.learner_id == learner_id
            ),
            key=lambda event: (event.occurred_at, str(event.event_id)),
        )
        event_ids = {event.event_id for event in ordered_events}
        self._processed_event_ids.difference_update(event_ids)

        state = None
        for event in ordered_events:
            state = self.apply(event)
        return state

    def restore(self, events: Iterable[EducationLearningEvent]) -> None:
        """Restore all learner states from durable history."""
        grouped: dict[tuple[UUID, UUID], list[EducationLearningEvent]] = {}
        for event in events:
            grouped.setdefault((event.tenant_id, event.learner_id), []).append(event)

        for (tenant_id, learner_id), learner_events in grouped.items():
            self.replay(
                learner_events,
                tenant_id=tenant_id,
                learner_id=learner_id,
            )

    def get(self, *, tenant_id: UUID, learner_id: UUID) -> LearnerSupervisionState | None:
        state = self._states.get((tenant_id, learner_id))
        return None if state is None else state.model_copy(deep=True)

    def list_for_tenant(self, *, tenant_id: UUID) -> list[LearnerSupervisionState]:
        states = [
            state.model_copy(deep=True)
            for (state_tenant_id, _), state in self._states.items()
            if state_tenant_id == tenant_id
        ]
        return sorted(states, key=lambda state: str(state.learner_id))
