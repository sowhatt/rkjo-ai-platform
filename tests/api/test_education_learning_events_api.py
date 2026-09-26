from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from fastapi.testclient import TestClient

from rkjo_api.education_dependencies import (
    get_education_assessment_learning_service,
    get_education_assessment_service,
    get_education_event_publisher,
)
from rkjo_api.main import app
from rkjo_education.assessment.models import (
    Assessment,
    Attempt,
    AttemptStatus,
    Question,
)
from rkjo_education.events import EducationEventType
from rkjo_education.intelligence.assessment_learning import (
    AssessmentLearningResult,
)
from rkjo_education.intelligence.learning_evaluation import (
    QuestionLearningResult,
)


TENANT_ID = uuid4()
LEARNER_ID = uuid4()
COURSE_ID = uuid4()
ASSESSMENT_ID = uuid4()
ATTEMPT_ID = uuid4()
QUESTION_ID = uuid4()
PROOF_ID = uuid4()


class FakeEventPublisher:
    def __init__(self) -> None:
        self.events = []

    def publish(self, event) -> None:
        self.events.append(event)

    def close(self) -> None:
        return None


@dataclass
class FakeAssessmentService:
    def start_attempt(self, *, tenant_id, assessment_id, learner_id):
        assert tenant_id == TENANT_ID
        assert assessment_id == ASSESSMENT_ID
        assert learner_id == LEARNER_ID
        return Attempt(
            tenant_id=tenant_id,
            assessment_id=assessment_id,
            learner_id=learner_id,
            id=ATTEMPT_ID,
        )


@dataclass
class FakeAssessmentLearningService:
    def submit_attempt(self, *, tenant_id, attempt_id, answers, evidence):
        assert tenant_id == TENANT_ID
        assert attempt_id == ATTEMPT_ID
        assert answers == {QUESTION_ID: "5"}
        attempt = Attempt(
            tenant_id=tenant_id,
            assessment_id=ASSESSMENT_ID,
            learner_id=LEARNER_ID,
            id=attempt_id,
            status=AttemptStatus.SUBMITTED,
            score=1,
            max_score=1,
            percentage=100,
        )
        return AssessmentLearningResult(
            attempt=attempt,
            learning=[
                QuestionLearningResult(
                    question_id=QUESTION_ID,
                    competency_code="MATH.ADD",
                    correct=True,
                    autonomy_score=100,
                    independently_correct=True,
                    mastery="provisional",
                    proof_required=True,
                    proof_challenge_id=PROOF_ID,
                )
            ],
        )


def _headers(monkeypatch):
    monkeypatch.setenv("RKJO_OPERATOR_API_KEY", "rkjo-operator-key")
    monkeypatch.setenv("RKJO_OPERATOR_TENANT_ID", str(TENANT_ID))
    return {"X-API-Key": "rkjo-operator-key"}


def test_start_attempt_publishes_assessment_started(monkeypatch):
    publisher = FakeEventPublisher()
    app.dependency_overrides[get_education_assessment_service] = lambda: FakeAssessmentService()
    app.dependency_overrides[get_education_event_publisher] = lambda: publisher
    try:
        with TestClient(app) as client:
            response = client.post(
                "/education/attempts",
                headers=_headers(monkeypatch),
                json={
                    "assessment_id": str(ASSESSMENT_ID),
                    "learner_id": str(LEARNER_ID),
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert [event.event_type for event in publisher.events] == [
        EducationEventType.ASSESSMENT_STARTED
    ]
    event = publisher.events[0]
    assert event.tenant_id == TENANT_ID
    assert event.learner_id == LEARNER_ID
    assert event.assessment_id == ASSESSMENT_ID


def test_submit_attempt_publishes_learning_chain(monkeypatch):
    publisher = FakeEventPublisher()
    app.dependency_overrides[get_education_assessment_learning_service] = (
        lambda: FakeAssessmentLearningService()
    )
    app.dependency_overrides[get_education_event_publisher] = lambda: publisher
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/education/attempts/{ATTEMPT_ID}/submit",
                headers=_headers(monkeypatch),
                json={
                    "answers": {str(QUESTION_ID): "5"},
                    "evidence": {
                        str(QUESTION_ID): {
                            "assistance_level": 0,
                            "hints_used": 0,
                            "attempt_count": 1,
                        }
                    },
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert [event.event_type for event in publisher.events] == [
        EducationEventType.ANSWER_SUBMITTED,
        EducationEventType.AUTONOMY_UPDATED,
        EducationEventType.MASTERY_UPDATED,
        EducationEventType.PROOF_REQUESTED,
        EducationEventType.ASSESSMENT_COMPLETED,
    ]
    autonomy = publisher.events[1]
    assert autonomy.payload == {"autonomy_score": 100}
    mastery = publisher.events[2]
    assert mastery.payload == {"mastery": "provisional"}
    proof = publisher.events[3]
    assert proof.payload == {"proof_challenge_id": str(PROOF_ID)}
