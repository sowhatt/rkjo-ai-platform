from uuid import uuid4


def test_assessment_journey_through_api(client, monkeypatch):
    tenant_id = uuid4()
    monkeypatch.setenv("RKJO_OPERATOR_TENANT_ID", str(tenant_id))
    headers = {"X-API-Key": "rkjo-operator-key"}

    course_id = uuid4()
    create = client.post(
        "/education/assessments",
        headers=headers,
        json={
            "course_id": str(course_id),
            "title": "Quiz addition",
            "questions": [
                {
                    "prompt": "2 + 2 ?",
                    "correct_answer": "4",
                    "points": 2,
                    "competency_code": "MATH.ADD",
                },
                {
                    "prompt": "3 + 1 ?",
                    "correct_answer": "4",
                    "points": 1,
                },
            ],
        },
    )
    assert create.status_code == 201
    assessment = create.json()
    assert assessment["max_score"] == 3

    start = client.post(
        "/education/attempts",
        headers=headers,
        json={
            "assessment_id": assessment["id"],
            "learner_id": str(uuid4()),
        },
    )
    assert start.status_code == 201
    attempt = start.json()

    submit = client.post(
        f"/education/attempts/{attempt['id']}/submit",
        headers=headers,
        json={
            "answers": {
                assessment["question_ids"][0]: "4",
                assessment["question_ids"][1]: "5",
            }
        },
    )
    assert submit.status_code == 200
    result = submit.json()
    assert result["score"] == 2
    assert result["max_score"] == 3
    assert result["percentage"] == 67
    assert result["status"] == "submitted"


def test_assessment_submit_accepts_learning_evidence(client, monkeypatch):
    tenant_id = uuid4()
    monkeypatch.setenv("RKJO_OPERATOR_TENANT_ID", str(tenant_id))
    headers = {"X-API-Key": "rkjo-operator-key"}

    create = client.post(
        "/education/assessments",
        headers=headers,
        json={
            "course_id": str(uuid4()),
            "title": "Preuve apprentissage",
            "questions": [
                {
                    "prompt": "5 + 5 ?",
                    "correct_answer": "10",
                    "points": 1,
                    "competency_code": "MATH.ADD",
                }
            ],
        },
    )
    assert create.status_code == 201
    assessment = create.json()
    question_id = assessment["question_ids"][0]

    start = client.post(
        "/education/attempts",
        headers=headers,
        json={
            "assessment_id": assessment["id"],
            "learner_id": str(uuid4()),
        },
    )
    assert start.status_code == 201
    attempt = start.json()

    submit = client.post(
        f"/education/attempts/{attempt['id']}/submit",
        headers=headers,
        json={
            "answers": {
                question_id: "10",
            },
            "evidence": {
                question_id: {
                    "assistance_level": 2,
                    "hints_used": 1,
                    "attempt_count": 2,
                    "response_time_seconds": 25,
                }
            },
        },
    )

    assert submit.status_code == 200
    result = submit.json()
    assert result["score"] == 1
    assert result["percentage"] == 100
    assert result["status"] == "submitted"


def test_assessment_submit_rejects_invalid_learning_evidence(client, monkeypatch):
    tenant_id = uuid4()
    monkeypatch.setenv("RKJO_OPERATOR_TENANT_ID", str(tenant_id))
    headers = {"X-API-Key": "rkjo-operator-key"}

    response = client.post(
        f"/education/attempts/{uuid4()}/submit",
        headers=headers,
        json={
            "answers": {},
            "evidence": {
                str(uuid4()): {
                    "assistance_level": 6,
                    "hints_used": -1,
                    "attempt_count": 0,
                    "response_time_seconds": -1,
                }
            },
        },
    )

    assert response.status_code == 422
