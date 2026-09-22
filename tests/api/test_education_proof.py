from uuid import uuid4

from rkjo_api.education_dependencies import (
    get_education_proof_service,
)
from rkjo_api.main import app
from rkjo_education.assessment.models import Assessment, Question
from rkjo_education.assessment.repository import (
    InMemoryAssessmentRepository,
)
from rkjo_education.intelligence.proof_application import (
    ProofApplicationService,
)
from rkjo_education.intelligence.proof_repository import (
    InMemoryProofChallengeRepository,
)


def build_proof_service(tenant_id):
    learner_id = uuid4()

    source = Question(
        tenant_id=tenant_id,
        prompt="2 + 3 ?",
        correct_answer="5",
        competency_code="MATH.ADD",
    )

    verification = Question(
        tenant_id=tenant_id,
        prompt="4 + 1 ?",
        correct_answer="5",
        competency_code="MATH.ADD",
    )

    assessment = Assessment(
        tenant_id=tenant_id,
        course_id=uuid4(),
        title="Addition",
        questions=[source, verification],
    )

    assessments = InMemoryAssessmentRepository()
    assessments.save_assessment(assessment)

    proofs = InMemoryProofChallengeRepository()

    service = ProofApplicationService(
        assessment_repository=assessments,
        proof_repository=proofs,
    )

    challenge = service.create_challenge(
        tenant_id=tenant_id,
        learner_id=learner_id,
        assessment_id=assessment.id,
        source_question_id=source.id,
        verification_question_id=verification.id,
    )

    return service, challenge


def test_proof_challenge_api_journey(client, monkeypatch):
    tenant_id = uuid4()

    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        str(tenant_id),
    )

    headers = {
        "X-API-Key": "rkjo-operator-key",
    }

    service, challenge = build_proof_service(tenant_id)

    app.dependency_overrides[
        get_education_proof_service
    ] = lambda: service

    try:
        response = client.get(
            f"/education/proof-challenges/{challenge.id}",
            headers=headers,
        )

        assert response.status_code == 200

        payload = response.json()

        assert payload["id"] == str(challenge.id)
        assert payload["prompt"] == "4 + 1 ?"
        assert payload["status"] == "required"

        assert "correct_answer" not in payload

        submit = client.post(
            (
                f"/education/proof-challenges/"
                f"{challenge.id}/submit"
            ),
            headers=headers,
            json={"answer": "5"},
        )

        assert submit.status_code == 200

        result = submit.json()

        assert result["challenge_id"] == str(challenge.id)
        assert result["status"] == "passed"
        assert result["independently_verified"] is True

        second = client.post(
            (
                f"/education/proof-challenges/"
                f"{challenge.id}/submit"
            ),
            headers=headers,
            json={"answer": "5"},
        )

        assert second.status_code == 409
    finally:
        app.dependency_overrides.pop(
            get_education_proof_service,
            None,
        )


def test_proof_challenge_is_tenant_scoped(
    client,
    monkeypatch,
):
    owner_tenant = uuid4()
    other_tenant = uuid4()

    service, challenge = build_proof_service(owner_tenant)

    app.dependency_overrides[
        get_education_proof_service
    ] = lambda: service

    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        str(other_tenant),
    )

    try:
        response = client.get(
            f"/education/proof-challenges/{challenge.id}",
            headers={"X-API-Key": "rkjo-operator-key"},
        )

        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(
            get_education_proof_service,
            None,
        )
