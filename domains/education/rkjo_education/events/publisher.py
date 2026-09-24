from __future__ import annotations

from rkjo_kernel.events.event_bus import EventBus

from .models import EducationLearningEvent


EDUCATION_EVENTS_QUEUE = "rkjo.education.learning.events"


class EducationEventPublisher:
    """Publishes canonical education events through the shared RKJO EventBus."""

    def __init__(
        self,
        event_bus: EventBus,
        *,
        queue_name: str = EDUCATION_EVENTS_QUEUE,
    ) -> None:
        normalized_queue = queue_name.strip()
        if not normalized_queue:
            raise ValueError("queue_name must not be empty")
        self._event_bus = event_bus
        self._queue_name = normalized_queue

    def publish(self, event: EducationLearningEvent) -> None:
        self._event_bus.publish(
            self._queue_name,
            event.model_dump_json(),
        )
