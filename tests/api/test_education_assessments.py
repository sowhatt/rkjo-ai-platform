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


def test_assessment_submit_returns_learning_and_proof_challenge(
    client,
    monkeypatch,
):
    tenant_id = uuid4()
    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        str(tenant_id),
    )
    headers = {
        "X-API-Key": "rkjo-operator-key",
    }

    create = client.post(
        "/education/assessments",
        headers=headers,
        json={
            "course_id": str(uuid4()),
            "title": "Validation autonomie",
            "questions": [
                {
                    "prompt": "2 + 3 ?",
                    "correct_answer": "5",
                    "points": 1,
                    "competency_code": "MATH.ADD",
                },
                {
                    "prompt": "4 + 1 ?",
                    "correct_answer": "5",
                    "points": 1,
                    "competency_code": "MATH.ADD",
                },
            ],
        },
    )

    assert create.status_code == 201
    assessment = create.json()

    learner_id = uuid4()

    start = client.post(
        "/education/attempts",
        headers=headers,
        json={
            "assessment_id": assessment["id"],
            "learner_id": str(learner_id),
        },
    )

    assert start.status_code == 201
    attempt = start.json()

    source_question_id = assessment["question_ids"][0]

    submit = client.post(
        f"/education/attempts/{attempt['id']}/submit",
        headers=headers,
        json={
            "answers": {
                source_question_id: "5",
            },
            "evidence": {
                source_question_id: {
                    "assistance_level": 3,
                    "hints_used": 1,
                    "attempt_count": 1,
                }
            },
        },
    )

    assert submit.status_code == 200

    result = submit.json()

    assert result["score"] == 1
    assert result["percentage"] == 50
    assert len(result["learning"]) == 1

    learning = result["learning"][0]

    assert learning["question_id"] == source_question_id
    assert learning["competency_code"] == "MATH.ADD"
    assert learning["correct"] is True
    assert learning["mastery"] == "developing"
    assert learning["proof_required"] is True
    assert learning["proof_challenge_id"] is not None

    proof = client.get(
        (
            "/education/proof-challenges/"
            f"{learning['proof_challenge_id']}"
        ),
        headers=headers,
    )

    assert proof.status_code == 200

    proof_payload = proof.json()

    assert proof_payload["competency_code"] == "MATH.ADD"
    assert proof_payload["status"] == "required"
    assert "correct_answer" not in proof_payload


def test_course_assessments_are_learner_safe(client, monkeypatch):
    tenant_id = uuid4()
    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        str(tenant_id),
    )
    headers = {"X-API-Key": "rkjo-operator-key"}
    course_id = uuid4()

    first = client.post(
        "/education/assessments",
        headers=headers,
        json={
            "course_id": str(course_id),
            "title": "Addition",
            "questions": [
                {
                    "prompt": "7 + 5 ?",
                    "correct_answer": "12",
                    "points": 1,
                    "competency_code": "MATH.ADD",
                }
            ],
        },
    )
    assert first.status_code == 201

    other = client.post(
        "/education/assessments",
        headers=headers,
        json={
            "course_id": str(uuid4()),
            "title": "Autre cours",
            "questions": [
                {
                    "prompt": "1 + 1 ?",
                    "correct_answer": "2",
                    "points": 1,
                    "competency_code": "MATH.ADD",
                }
            ],
        },
    )
    assert other.status_code == 201

    response = client.get(
        f"/education/courses/{course_id}/assessments",
        headers=headers,
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["title"] == "Addition"
    assert payload[0]["course_id"] == str(course_id)
    assert payload[0]["questions"][0]["prompt"] == "7 + 5 ?"
    assert payload[0]["questions"][0]["competency_code"] == "MATH.ADD"

    serialized = str(payload).casefold()
    assert "correct_answer" not in serialized
    assert '"12"' not in serialized


def test_course_assessments_are_tenant_scoped(client, monkeypatch):
    first_tenant = uuid4()
    second_tenant = uuid4()
    course_id = uuid4()

    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        str(first_tenant),
    )
    headers = {"X-API-Key": "rkjo-operator-key"}

    create = client.post(
        "/education/assessments",
        headers=headers,
        json={
            "course_id": str(course_id),
            "title": "Privé",
            "questions": [
                {
                    "prompt": "8 + 2 ?",
                    "correct_answer": "10",
                    "points": 1,
                    "competency_code": "MATH.ADD",
                }
            ],
        },
    )
    assert create.status_code == 201

    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        str(second_tenant),
    )

    response = client.get(
        f"/education/courses/{course_id}/assessments",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == []
