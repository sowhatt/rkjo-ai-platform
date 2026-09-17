from uuid import uuid4


def test_education_learner_journey_through_api(client, monkeypatch):
    tenant_id = uuid4()
    monkeypatch.setenv("RKJO_OPERATOR_TENANT_ID", str(tenant_id))
    headers = {"X-API-Key": "rkjo-operator-key"}

    create_learner = client.post(
        "/education/learners",
        headers=headers,
        json={
            "first_name": "Awa",
            "last_name": "Mensah",
            "level": "CE1",
        },
    )
    assert create_learner.status_code == 201
    learner = create_learner.json()
    assert learner["tenant_id"] == str(tenant_id)

    curriculum_id = uuid4()
    enrollment = client.post(
        "/education/enrollments",
        headers=headers,
        json={
            "learner_id": learner["id"],
            "curriculum_id": str(curriculum_id),
        },
    )
    assert enrollment.status_code == 201

    competency = client.post(
        "/education/competencies",
        headers=headers,
        json={
            "code": "MATH.ADD",
            "label": "Additionner des nombres entiers",
        },
    )
    assert competency.status_code == 201

    course_id = uuid4()
    progress = client.post(
        "/education/progress",
        headers=headers,
        json={
            "learner_id": learner["id"],
            "course_id": str(course_id),
            "completion_percent": 100,
            "competency_scores": {"MATH.ADD": 90},
        },
    )
    assert progress.status_code == 200
    assert progress.json()["completion_percent"] == 100
    assert progress.json()["competency_scores"]["MATH.ADD"] == 90


def test_education_requires_authentication(client):
    response = client.get(f"/education/learners/{uuid4()}")
    assert response.status_code == 401


def test_education_write_requires_operator_role(client, monkeypatch):
    monkeypatch.setenv("RKJO_VIEWER_TENANT_ID", str(uuid4()))
    response = client.post(
        "/education/learners",
        headers={"X-API-Key": "rkjo-viewer-key"},
        json={
            "first_name": "Awa",
            "last_name": "Mensah",
            "level": "CE1",
        },
    )
    assert response.status_code == 403
