from __future__ import annotations

from rkjo_kernel.events.event_bus import EventBus

from rkjo_education.events import (
    EDUCATION_EVENTS_QUEUE,
    EducationLearningEvent,
)
from rkjo_education.supervision import LearnerSupervisionProjection
from rkjo_education.supervision.history import PostgresLearningEventHistory


class EducationSupervisionEventConsumer:
    """Projects canonical education events into the live teacher read model."""

    def __init__(
        self,
        *,
        event_bus: EventBus,
        projection: LearnerSupervisionProjection,
        queue_name: str = EDUCATION_EVENTS_QUEUE,
        history: PostgresLearningEventHistory | None = None,
    ) -> None:
        normalized_queue = queue_name.strip()
        if not normalized_queue:
            raise ValueError("queue_name must not be empty")
        self._event_bus = event_bus
        self._projection = projection
        self._queue_name = normalized_queue
        self._history = history

    def consume(self) -> None:
        self._event_bus.consume(
            self._queue_name,
            self._handle_message,
        )

    def _handle_message(self, message: str) -> None:
        event = EducationLearningEvent.model_validate_json(message)
        if self._history is not None:
            self._history.append(event)
        self._projection.apply(event)
