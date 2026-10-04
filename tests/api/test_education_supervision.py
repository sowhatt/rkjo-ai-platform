from datetime import timedelta
from uuid import UUID, uuid4

from rkjo_api.education_supervision import (
    enrich_teacher_interventions,
    get_supervision_projection,
)
from rkjo_api.main import app
from rkjo_education.events import EducationEventType, EducationLearningEvent
from rkjo_education.supervision import LearnerSupervisionProjection
from rkjo_education.supervision.interventions import (
    TeacherIntervention,
    TeacherInterventionType,
)


TENANT_A = UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = UUID("22222222-2222-2222-2222-222222222222")


def headers(api_key="rkjo-admin-key"):
    return {"X-API-Key": api_key}


def projection_with_states():
    projection = LearnerSupervisionProjection()
    learner_a = uuid4()
    learner_b = uuid4()
    projection.apply(EducationLearningEvent(
        event_type=EducationEventType.SESSION_STARTED,
        tenant_id=TENANT_A,
        learner_id=learner_a,
    ))
    projection.apply(EducationLearningEvent(
        event_type=EducationEventType.AUTONOMY_UPDATED,
        tenant_id=TENANT_A,
        learner_id=learner_a,
        payload={"autonomy_score": 82},
    ))
    projection.apply(EducationLearningEvent(
        event_type=EducationEventType.SESSION_STARTED,
        tenant_id=TENANT_B,
        learner_id=learner_b,
    ))
    return projection, learner_a, learner_b


def test_supervision_learner_snapshot_is_tenant_scoped(client, monkeypatch):
    projection, learner_a, _ = projection_with_states()
    app.dependency_overrides[get_supervision_projection] = lambda: projection
    monkeypatch.setenv("RKJO_ADMIN_TENANT_ID", str(TENANT_A))
    try:
        response = client.get(
            f"/education/supervision/learners/{learner_a}/snapshot",
            headers=headers(),
        )
    finally:
        app.dependency_overrides.pop(get_supervision_projection, None)

    assert response.status_code == 200
    body = response.json()
    assert body["learner_id"] == str(learner_a)
    assert body["tenant_id"] == str(TENANT_A)
    assert body["active"] is True
    assert body["autonomy_score"] == 82


def test_supervision_learner_snapshot_hides_other_tenant(client, monkeypatch):
    projection, _, learner_b = projection_with_states()
    app.dependency_overrides[get_supervision_projection] = lambda: projection
    monkeypatch.setenv("RKJO_ADMIN_TENANT_ID", str(TENANT_A))
    try:
        response = client.get(
            f"/education/supervision/learners/{learner_b}/snapshot",
            headers=headers(),
        )
    finally:
        app.dependency_overrides.pop(get_supervision_projection, None)

    assert response.status_code == 404


def test_supervision_tenant_snapshot_never_leaks_other_tenant(client, monkeypatch):
    projection, learner_a, learner_b = projection_with_states()
    app.dependency_overrides[get_supervision_projection] = lambda: projection
    monkeypatch.setenv("RKJO_ADMIN_TENANT_ID", str(TENANT_A))
    try:
        response = client.get(
            "/education/supervision/snapshot",
            headers=headers(),
        )
    finally:
        app.dependency_overrides.pop(get_supervision_projection, None)

    assert response.status_code == 200
    learner_ids = {item["learner_id"] for item in response.json()}
    assert learner_ids == {str(learner_a)}
    assert str(learner_b) not in learner_ids


def test_supervision_snapshot_requires_uuid_tenant(client, monkeypatch):
    projection = LearnerSupervisionProjection()
    app.dependency_overrides[get_supervision_projection] = lambda: projection
    monkeypatch.setenv("RKJO_ADMIN_TENANT_ID", "tenant-a")
    try:
        response = client.get(
            "/education/supervision/snapshot",
            headers=headers(),
        )
    finally:
        app.dependency_overrides.pop(get_supervision_projection, None)

    assert response.status_code == 400


def _answer_event(*, intervention, assessment_id, question_id, competency_code, correct, seconds=1):
    return EducationLearningEvent(
        event_type=EducationEventType.ANSWER_SUBMITTED,
        tenant_id=intervention.tenant_id,
        learner_id=intervention.learner_id,
        assessment_id=assessment_id,
        question_id=question_id,
        competency_code=competency_code,
        occurred_at=intervention.requested_at + timedelta(seconds=seconds),
        payload={"correct": correct},
    )


def test_consolidation_ignores_old_and_unrelated_answers():
    assessment_id, question_id = uuid4(), uuid4()
    intervention = TeacherIntervention(
        tenant_id=TENANT_A,
        learner_id=uuid4(),
        intervention_type=TeacherInterventionType.ASSIGN_CONSOLIDATION,
        message=str(assessment_id),
        target_assessment_id=assessment_id,
        target_question_id=question_id,
        competency_code="MATH.ADD",
    )
    old_answer = EducationLearningEvent(
        event_type=EducationEventType.ANSWER_SUBMITTED,
        tenant_id=intervention.tenant_id,
        learner_id=intervention.learner_id,
        assessment_id=assessment_id,
        question_id=question_id,
        competency_code="MATH.ADD",
        occurred_at=intervention.requested_at - timedelta(seconds=1),
        payload={"correct": True},
    )
    unrelated = _answer_event(
        intervention=intervention,
        assessment_id=assessment_id,
        question_id=uuid4(),
        competency_code="MATH.ADD",
        correct=True,
    )
    enriched = enrich_teacher_interventions([intervention], [old_answer, unrelated])[0]
    assert enriched.status.value == "requested"
    assert enriched.result_status is None


def test_consolidation_correlates_exact_answer_autonomy_and_mastery():
    assessment_id, question_id = uuid4(), uuid4()
    intervention = TeacherIntervention(
        tenant_id=TENANT_A,
        learner_id=uuid4(),
        intervention_type=TeacherInterventionType.ASSIGN_CONSOLIDATION,
        message=str(assessment_id),
        target_assessment_id=assessment_id,
        target_question_id=question_id,
        competency_code="MATH.ADD",
    )
    answer = _answer_event(
        intervention=intervention,
        assessment_id=assessment_id,
        question_id=question_id,
        competency_code="MATH.ADD",
        correct=True,
    )
    autonomy = EducationLearningEvent(
        event_type=EducationEventType.AUTONOMY_UPDATED,
        tenant_id=intervention.tenant_id,
        learner_id=intervention.learner_id,
        assessment_id=assessment_id,
        question_id=question_id,
        competency_code="MATH.ADD",
        occurred_at=answer.occurred_at + timedelta(milliseconds=1),
        payload={"autonomy_score": 90},
    )
    mastery = EducationLearningEvent(
        event_type=EducationEventType.MASTERY_UPDATED,
        tenant_id=intervention.tenant_id,
        learner_id=intervention.learner_id,
        assessment_id=assessment_id,
        question_id=question_id,
        competency_code="MATH.ADD",
        occurred_at=answer.occurred_at + timedelta(milliseconds=2),
        payload={"mastery": "provisional"},
    )
    enriched = enrich_teacher_interventions(
        [intervention], [answer, autonomy, mastery]
    )[0]
    assert enriched.status.value == "acknowledged"
    assert enriched.result_status == "passed"
    assert enriched.result_autonomy_score == 90
    assert enriched.result_mastery == "provisional"


def test_consolidation_wrong_target_answer_is_failed():
    assessment_id, question_id = uuid4(), uuid4()
    intervention = TeacherIntervention(
        tenant_id=TENANT_A,
        learner_id=uuid4(),
        intervention_type=TeacherInterventionType.ASSIGN_CONSOLIDATION,
        message=str(assessment_id),
        target_assessment_id=assessment_id,
        target_question_id=question_id,
        competency_code="MATH.ADD",
    )
    answer = _answer_event(
        intervention=intervention,
        assessment_id=assessment_id,
        question_id=question_id,
        competency_code="MATH.ADD",
        correct=False,
    )
    enriched = enrich_teacher_interventions([intervention], [answer])[0]
    assert enriched.status.value == "acknowledged"
    assert enriched.result_status == "failed"


def test_legacy_consolidation_falls_back_to_message_assessment():
    assessment_id, question_id = uuid4(), uuid4()
    intervention = TeacherIntervention(
        tenant_id=TENANT_A,
        learner_id=uuid4(),
        intervention_type=TeacherInterventionType.ASSIGN_CONSOLIDATION,
        message=str(assessment_id),
    )
    answer = _answer_event(
        intervention=intervention,
        assessment_id=assessment_id,
        question_id=question_id,
        competency_code="MATH.ADD",
        correct=True,
    )
    enriched = enrich_teacher_interventions([intervention], [answer])[0]
    assert enriched.status.value == "acknowledged"
    assert enriched.result_status == "passed"
