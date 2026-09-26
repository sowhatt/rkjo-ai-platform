from uuid import UUID, uuid4

from rkjo_api.education_supervision import get_supervision_projection
from rkjo_api.main import app
from rkjo_education.events import EducationEventType, EducationLearningEvent
from rkjo_education.supervision import LearnerSupervisionProjection


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
