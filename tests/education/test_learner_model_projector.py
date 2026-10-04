from datetime import datetime, timedelta, timezone
from uuid import uuid4

from rkjo_education.events import EducationEventType, EducationLearningEvent
from rkjo_education.intelligence.learner_model import LearnerModelProjector


def event(kind, *, correct=None, autonomy=None, question=None, at=None):
    payload = {}
    if correct is not None:
        payload["correct"] = correct
    if autonomy is not None:
        payload["autonomy_score"] = autonomy
    return EducationLearningEvent(
        event_type=kind,
        tenant_id=TENANT,
        learner_id=LEARNER,
        competency_code="MATH.ADD",
        question_id=question,
        occurred_at=at or NOW,
        payload=payload,
    )


TENANT = uuid4()
LEARNER = uuid4()
NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def test_projector_uses_durable_answers_and_autonomy():
    q1, q2 = uuid4(), uuid4()
    state = LearnerModelProjector().project([
        event(EducationEventType.ANSWER_SUBMITTED, correct=True, question=q1),
        event(EducationEventType.AUTONOMY_UPDATED, autonomy=100, question=q1),
        event(EducationEventType.ANSWER_SUBMITTED, correct=True, question=q2),
        event(EducationEventType.AUTONOMY_UPDATED, autonomy=50, question=q2),
    ], competency_code="MATH.ADD", now=NOW)
    assert state.autonomy == .75
    assert state.latest_correct is True
    assert state.latest_help == .5
    assert state.mastery <= .75


def test_projector_proof_unlocks_mastery_cap():
    q = uuid4()
    events = []
    for day in range(10):
        events += [
            event(EducationEventType.ANSWER_SUBMITTED, correct=True, question=q, at=NOW-timedelta(days=10-day)),
            event(EducationEventType.AUTONOMY_UPDATED, autonomy=100, question=q, at=NOW-timedelta(days=10-day)),
        ]
    capped = LearnerModelProjector().project(events, competency_code="MATH.ADD", now=NOW)
    passed = LearnerModelProjector().project(
        events + [event(EducationEventType.PROOF_PASSED, at=NOW)],
        competency_code="MATH.ADD",
        now=NOW,
    )
    assert capped.mastery == .75
    assert passed.mastery > .75
    assert passed.successful_proof is True


def test_projector_counts_consecutive_failures():
    q1, q2, q3 = uuid4(), uuid4(), uuid4()
    state = LearnerModelProjector().project([
        event(EducationEventType.ANSWER_SUBMITTED, correct=True, question=q1),
        event(EducationEventType.ANSWER_SUBMITTED, correct=False, question=q2),
        event(EducationEventType.ANSWER_SUBMITTED, correct=False, question=q3),
    ], competency_code="MATH.ADD", now=NOW)
    assert state.consecutive_failures == 2


def test_projector_retention_decays_after_success():
    q = uuid4()
    state = LearnerModelProjector().project([
        event(EducationEventType.ANSWER_SUBMITTED, correct=True, question=q, at=NOW-timedelta(days=2)),
        event(EducationEventType.AUTONOMY_UPDATED, autonomy=100, question=q, at=NOW-timedelta(days=2)),
    ], competency_code="MATH.ADD", now=NOW)
    assert state.retention < .60
