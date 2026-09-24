from uuid import uuid4

from rkjo_education.events import (
    EDUCATION_EVENTS_QUEUE,
    EducationEventPublisher,
    EducationEventType,
    EducationLearningEvent,
)


class RecordingEventBus:
    def __init__(self):
        self.published = []

    def publish(self, queue_name, message):
        self.published.append((queue_name, message))


def test_learning_event_contains_canonical_supervision_context():
    tenant_id = uuid4()
    learner_id = uuid4()
    course_id = uuid4()
    session_id = uuid4()

    event = EducationLearningEvent(
        event_type=EducationEventType.SESSION_STARTED,
        tenant_id=tenant_id,
        learner_id=learner_id,
        course_id=course_id,
        session_id=session_id,
        payload={"source": "pwa"},
    )

    assert event.event_id is not None
    assert event.tenant_id == tenant_id
    assert event.learner_id == learner_id
    assert event.course_id == course_id
    assert event.session_id == session_id
    assert event.event_type == EducationEventType.SESSION_STARTED
    assert event.occurred_at.tzinfo is not None


def test_publisher_uses_shared_event_bus_and_json_envelope():
    bus = RecordingEventBus()
    publisher = EducationEventPublisher(bus)
    event = EducationLearningEvent(
        event_type=EducationEventType.ASSESSMENT_STARTED,
        tenant_id=uuid4(),
        learner_id=uuid4(),
        assessment_id=uuid4(),
    )

    publisher.publish(event)

    assert len(bus.published) == 1
    queue_name, body = bus.published[0]
    assert queue_name == EDUCATION_EVENTS_QUEUE

    restored = EducationLearningEvent.model_validate_json(body)
    assert restored == event


def test_event_payload_is_not_shared_between_events():
    first = EducationLearningEvent(
        event_type=EducationEventType.TUTOR_REQUESTED,
        tenant_id=uuid4(),
        learner_id=uuid4(),
    )
    second = EducationLearningEvent(
        event_type=EducationEventType.TUTOR_REQUESTED,
        tenant_id=uuid4(),
        learner_id=uuid4(),
    )

    first.payload["assistance"] = "hint"

    assert second.payload == {}


def test_publisher_rejects_blank_queue_name():
    bus = RecordingEventBus()

    try:
        EducationEventPublisher(bus, queue_name="   ")
    except ValueError as exc:
        assert str(exc) == "queue_name must not be empty"
    else:
        raise AssertionError("blank queue name should be rejected")
