from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from rkjo_api.education_dependencies import get_education_event_publisher
from rkjo_api.main import app
from rkjo_education.events import EducationEventType


TENANT_ID = uuid4()
LEARNER_ID = uuid4()
COURSE_ID = uuid4()
ASSESSMENT_ID = uuid4()
QUESTION_ID = uuid4()


class FakeEventPublisher:
    def __init__(self) -> None:
        self.events = []

    def publish(self, event) -> None:
        self.events.append(event)

    def close(self) -> None:
        return None


def test_hint_request_publishes_canonical_event(monkeypatch):
    publisher = FakeEventPublisher()
    monkeypatch.setenv("RKJO_OPERATOR_API_KEY", "rkjo-operator-key")
    monkeypatch.setenv("RKJO_OPERATOR_TENANT_ID", str(TENANT_ID))
    app.dependency_overrides[get_education_event_publisher] = lambda: publisher
    try:
        with TestClient(app) as client:
            response = client.post(
                "/education/hints",
                headers={"X-API-Key": "rkjo-operator-key"},
                json={
                    "learner_id": str(LEARNER_ID),
                    "course_id": str(COURSE_ID),
                    "assessment_id": str(ASSESSMENT_ID),
                    "question_id": str(QUESTION_ID),
                    "competency_code": "MATH.ADD",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"recorded": True}
    assert len(publisher.events) == 1
    event = publisher.events[0]
    assert event.event_type == EducationEventType.HINT_REQUESTED
    assert event.tenant_id == TENANT_ID
    assert event.learner_id == LEARNER_ID
    assert event.course_id == COURSE_ID
    assert event.assessment_id == ASSESSMENT_ID
    assert event.question_id == QUESTION_ID
    assert event.competency_code == "MATH.ADD"
