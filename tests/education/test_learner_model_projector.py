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


def test_projector_uses_v23_attempt_scores_by_help_level():
    q1, q2, q3, q4 = uuid4(), uuid4(), uuid4(), uuid4()
    state = LearnerModelProjector().project([
        event(EducationEventType.ANSWER_SUBMITTED, correct=True, question=q1),
        event(EducationEventType.AUTONOMY_UPDATED, autonomy=100, question=q1),
        event(EducationEventType.ANSWER_SUBMITTED, correct=True, question=q2),
        event(EducationEventType.AUTONOMY_UPDATED, autonomy=75, question=q2),
        event(EducationEventType.ANSWER_SUBMITTED, correct=True, question=q3),
        event(EducationEventType.AUTONOMY_UPDATED, autonomy=50, question=q3),
        event(EducationEventType.ANSWER_SUBMITTED, correct=True, question=q4),
        event(EducationEventType.AUTONOMY_UPDATED, autonomy=0, question=q4),
    ], competency_code="MATH.ADD", now=NOW)

    expected_scores = [0.7, 0.5, 0.3, 0.1]
    numerator = 0.30
    denominator = 1.0
    for rank, score in enumerate(reversed(expected_scores)):
        decay = 0.85 ** rank
        numerator += decay * score
        denominator += decay
    assert state.mastery == min(numerator / denominator, 0.75)
    assert state.autonomy == (1.0 + 0.75 + 0.5 + 0.0) / 4


def test_projector_reconciles_last_success_after_answer_then_autonomy():
    q = uuid4()
    state = LearnerModelProjector().project([
        event(EducationEventType.ANSWER_SUBMITTED, correct=True, question=q, at=NOW-timedelta(days=1)),
        event(EducationEventType.AUTONOMY_UPDATED, autonomy=100, question=q, at=NOW-timedelta(days=1)),
    ], competency_code="MATH.ADD", now=NOW)
    assert state.retention > 0.60


def test_retention_stability_grows_after_spaced_no_help_success():
    from datetime import timedelta
    tenant_id = uuid4()
    learner_id = uuid4()
    competency = "MATH.ADD"
    now = datetime.now(timezone.utc)
    q1, q2 = uuid4(), uuid4()
    events = [
        EducationLearningEvent(
            event_type=EducationEventType.ANSWER_SUBMITTED,
            tenant_id=tenant_id, learner_id=learner_id,
            competency_code=competency, question_id=q1,
            occurred_at=now - timedelta(days=4),
            payload={"correct": True},
        ),
        EducationLearningEvent(
            event_type=EducationEventType.AUTONOMY_UPDATED,
            tenant_id=tenant_id, learner_id=learner_id,
            competency_code=competency, question_id=q1,
            occurred_at=now - timedelta(days=4),
            payload={"autonomy_score": 100},
        ),
        EducationLearningEvent(
            event_type=EducationEventType.ANSWER_SUBMITTED,
            tenant_id=tenant_id, learner_id=learner_id,
            competency_code=competency, question_id=q2,
            occurred_at=now - timedelta(days=2),
            payload={"correct": True},
        ),
        EducationLearningEvent(
            event_type=EducationEventType.AUTONOMY_UPDATED,
            tenant_id=tenant_id, learner_id=learner_id,
            competency_code=competency, question_id=q2,
            occurred_at=now - timedelta(days=2),
            payload={"autonomy_score": 100},
        ),
    ]
    state = LearnerModelProjector().project(events, competency_code=competency, now=now)
    assert state.retention > 0.60


def test_retention_failure_shrinks_stability_floor_to_one_day():
    from datetime import timedelta
    tenant_id = uuid4()
    learner_id = uuid4()
    competency = "MATH.ADD"
    now = datetime.now(timezone.utc)
    q1, q2 = uuid4(), uuid4()
    events = [
        EducationLearningEvent(
            event_type=EducationEventType.ANSWER_SUBMITTED,
            tenant_id=tenant_id, learner_id=learner_id,
            competency_code=competency, question_id=q1,
            occurred_at=now - timedelta(days=2),
            payload={"correct": True},
        ),
        EducationLearningEvent(
            event_type=EducationEventType.AUTONOMY_UPDATED,
            tenant_id=tenant_id, learner_id=learner_id,
            competency_code=competency, question_id=q1,
            occurred_at=now - timedelta(days=2),
            payload={"autonomy_score": 100},
        ),
        EducationLearningEvent(
            event_type=EducationEventType.ANSWER_SUBMITTED,
            tenant_id=tenant_id, learner_id=learner_id,
            competency_code=competency, question_id=q2,
            occurred_at=now - timedelta(days=1),
            payload={"correct": False},
        ),
    ]
    state = LearnerModelProjector().project(events, competency_code=competency, now=now)
    assert state.retention < 0.20
