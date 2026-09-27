import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from rkjo_education.events import EducationEventType, EducationLearningEvent
from rkjo_education.supervision import LearnerSupervisionProjection
from rkjo_education.supervision.history import PostgresLearningEventHistory


DATABASE_URL = os.getenv("RKJO_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="RKJO_DATABASE_URL is not configured",
)


def make_event(
    event_type: EducationEventType,
    *,
    tenant_id,
    learner_id,
    occurred_at,
    payload=None,
):
    return EducationLearningEvent(
        event_type=event_type,
        tenant_id=tenant_id,
        learner_id=learner_id,
        occurred_at=occurred_at,
        payload=payload or {},
    )


def test_history_is_idempotent_ordered_and_tenant_isolated():
    history = PostgresLearningEventHistory(DATABASE_URL)
    history.initialize_schema()

    tenant_a = uuid4()
    tenant_b = uuid4()
    learner_id = uuid4()
    now = datetime.now(timezone.utc)

    later = make_event(
        EducationEventType.HINT_REQUESTED,
        tenant_id=tenant_a,
        learner_id=learner_id,
        occurred_at=now + timedelta(seconds=2),
    )
    earlier = make_event(
        EducationEventType.SESSION_STARTED,
        tenant_id=tenant_a,
        learner_id=learner_id,
        occurred_at=now,
    )
    other_tenant = make_event(
        EducationEventType.AUTONOMY_UPDATED,
        tenant_id=tenant_b,
        learner_id=learner_id,
        occurred_at=now + timedelta(seconds=1),
        payload={"autonomy_score": 12},
    )

    history.append(later)
    history.append(earlier)
    history.append(earlier)
    history.append(other_tenant)

    tenant_a_events = history.list_for_learner(
        tenant_id=tenant_a,
        learner_id=learner_id,
    )
    tenant_b_events = history.list_for_learner(
        tenant_id=tenant_b,
        learner_id=learner_id,
    )

    assert [event.event_id for event in tenant_a_events] == [
        earlier.event_id,
        later.event_id,
    ]
    assert [event.event_id for event in tenant_b_events] == [
        other_tenant.event_id,
    ]


def test_durable_history_restores_projection_after_restart():
    history = PostgresLearningEventHistory(DATABASE_URL)
    history.initialize_schema()

    tenant_id = uuid4()
    learner_id = uuid4()
    now = datetime.now(timezone.utc)

    events = [
        make_event(
            EducationEventType.SESSION_STARTED,
            tenant_id=tenant_id,
            learner_id=learner_id,
            occurred_at=now,
        ),
        make_event(
            EducationEventType.ANSWER_SUBMITTED,
            tenant_id=tenant_id,
            learner_id=learner_id,
            occurred_at=now + timedelta(seconds=1),
        ),
        make_event(
            EducationEventType.AUTONOMY_UPDATED,
            tenant_id=tenant_id,
            learner_id=learner_id,
            occurred_at=now + timedelta(seconds=2),
            payload={"autonomy_score": 70},
        ),
        make_event(
            EducationEventType.MASTERY_UPDATED,
            tenant_id=tenant_id,
            learner_id=learner_id,
            occurred_at=now + timedelta(seconds=3),
            payload={"mastery": "developing"},
        ),
        make_event(
            EducationEventType.PROOF_PASSED,
            tenant_id=tenant_id,
            learner_id=learner_id,
            occurred_at=now + timedelta(seconds=4),
        ),
    ]
    for item in events:
        history.append(item)

    restarted_projection = LearnerSupervisionProjection()
    restarted_projection.restore(history.list_all())
    state = restarted_projection.get(
        tenant_id=tenant_id,
        learner_id=learner_id,
    )

    assert state is not None
    assert state.active is True
    assert state.answers_submitted == 1
    assert state.autonomy_score == 70
    assert state.mastery == "developing"
    assert state.proof_status == "passed"
