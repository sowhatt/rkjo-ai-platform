from uuid import uuid4

from rkjo_education.events import (
    EDUCATION_EVENTS_QUEUE,
    EducationEventType,
    EducationLearningEvent,
)
from rkjo_education.supervision import (
    EducationSupervisionEventConsumer,
    LearnerSupervisionProjection,
)
from rkjo_kernel.events.event_bus import EventBus


class FakeEventBus(EventBus):
    def __init__(self, messages: list[str]) -> None:
        self.messages = messages
        self.queue_name = None

    def publish(self, queue_name: str, message: str) -> None:
        raise NotImplementedError

    def consume(self, queue_name: str, callback) -> None:
        self.queue_name = queue_name
        for message in self.messages:
            callback(message)

    def publish_agent_message(self, queue_name: str, message) -> None:
        raise NotImplementedError

    def consume_agent_messages(self, queue_name: str, callback) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass


def test_consumer_projects_canonical_event_from_shared_bus():
    tenant_id = uuid4()
    learner_id = uuid4()
    event = EducationLearningEvent(
        event_type=EducationEventType.SESSION_STARTED,
        tenant_id=tenant_id,
        learner_id=learner_id,
        session_id=uuid4(),
    )
    bus = FakeEventBus([event.model_dump_json()])
    projection = LearnerSupervisionProjection()

    EducationSupervisionEventConsumer(
        event_bus=bus,
        projection=projection,
    ).consume()

    state = projection.get(
        tenant_id=tenant_id,
        learner_id=learner_id,
    )
    assert bus.queue_name == EDUCATION_EVENTS_QUEUE
    assert state is not None
    assert state.active is True
    assert state.last_event_id == event.event_id


def test_consumer_rejects_invalid_event_before_projection():
    bus = FakeEventBus(["not-json"])
    projection = LearnerSupervisionProjection()

    consumer = EducationSupervisionEventConsumer(
        event_bus=bus,
        projection=projection,
    )

    try:
        consumer.consume()
    except ValueError:
        pass
    else:
        raise AssertionError("invalid canonical event must fail")
