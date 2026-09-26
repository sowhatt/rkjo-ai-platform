from uuid import uuid4

from rkjo_education.events import EducationEventType, EducationLearningEvent
from rkjo_education.supervision import LearnerSupervisionProjection


def event(event_type, *, tenant_id, learner_id, payload=None, **kwargs):
    return EducationLearningEvent(
        event_type=event_type,
        tenant_id=tenant_id,
        learner_id=learner_id,
        payload=payload or {},
        **kwargs,
    )


def test_projection_builds_live_learner_state():
    tenant_id = uuid4()
    learner_id = uuid4()
    course_id = uuid4()
    session_id = uuid4()
    projection = LearnerSupervisionProjection()

    projection.apply(event(
        EducationEventType.SESSION_STARTED,
        tenant_id=tenant_id,
        learner_id=learner_id,
        course_id=course_id,
        session_id=session_id,
    ))
    projection.apply(event(
        EducationEventType.ANSWER_SUBMITTED,
        tenant_id=tenant_id,
        learner_id=learner_id,
    ))
    projection.apply(event(
        EducationEventType.HINT_REQUESTED,
        tenant_id=tenant_id,
        learner_id=learner_id,
    ))
    projection.apply(event(
        EducationEventType.TUTOR_REQUESTED,
        tenant_id=tenant_id,
        learner_id=learner_id,
    ))
    projection.apply(event(
        EducationEventType.AUTONOMY_UPDATED,
        tenant_id=tenant_id,
        learner_id=learner_id,
        payload={"autonomy_score": 81},
    ))
    state = projection.apply(event(
        EducationEventType.MASTERY_UPDATED,
        tenant_id=tenant_id,
        learner_id=learner_id,
        payload={"mastery": "provisional"},
    ))

    assert state.active is True
    assert state.course_id == course_id
    assert state.session_id == session_id
    assert state.answers_submitted == 1
    assert state.hints_requested == 1
    assert state.tutor_requests == 1
    assert state.autonomy_score == 81
    assert state.mastery == "provisional"


def test_projection_tracks_proof_lifecycle_and_session_completion():
    tenant_id = uuid4()
    learner_id = uuid4()
    projection = LearnerSupervisionProjection()

    projection.apply(event(
        EducationEventType.SESSION_STARTED,
        tenant_id=tenant_id,
        learner_id=learner_id,
    ))
    projection.apply(event(
        EducationEventType.PROOF_REQUESTED,
        tenant_id=tenant_id,
        learner_id=learner_id,
    ))
    state = projection.apply(event(
        EducationEventType.PROOF_PASSED,
        tenant_id=tenant_id,
        learner_id=learner_id,
    ))
    assert state.proof_status == "passed"

    state = projection.apply(event(
        EducationEventType.SESSION_COMPLETED,
        tenant_id=tenant_id,
        learner_id=learner_id,
    ))
    assert state.active is False


def test_projection_is_idempotent_for_duplicate_event():
    tenant_id = uuid4()
    learner_id = uuid4()
    projection = LearnerSupervisionProjection()
    submitted = event(
        EducationEventType.ANSWER_SUBMITTED,
        tenant_id=tenant_id,
        learner_id=learner_id,
    )

    projection.apply(submitted)
    state = projection.apply(submitted)

    assert state.answers_submitted == 1


def test_projection_is_strictly_tenant_isolated():
    learner_id = uuid4()
    tenant_a = uuid4()
    tenant_b = uuid4()
    projection = LearnerSupervisionProjection()

    projection.apply(event(
        EducationEventType.AUTONOMY_UPDATED,
        tenant_id=tenant_a,
        learner_id=learner_id,
        payload={"autonomy_score": 91},
    ))
    projection.apply(event(
        EducationEventType.AUTONOMY_UPDATED,
        tenant_id=tenant_b,
        learner_id=learner_id,
        payload={"autonomy_score": 34},
    ))

    assert projection.get(tenant_id=tenant_a, learner_id=learner_id).autonomy_score == 91
    assert projection.get(tenant_id=tenant_b, learner_id=learner_id).autonomy_score == 34


def test_projection_ignores_invalid_autonomy_payload():
    tenant_id = uuid4()
    learner_id = uuid4()
    projection = LearnerSupervisionProjection()

    state = projection.apply(event(
        EducationEventType.AUTONOMY_UPDATED,
        tenant_id=tenant_id,
        learner_id=learner_id,
        payload={"autonomy_score": 150},
    ))

    assert state.autonomy_score is None
