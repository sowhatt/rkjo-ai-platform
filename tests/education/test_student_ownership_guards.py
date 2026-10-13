"""Ownership validation of learner attempts and independent proofs."""
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from rkjo_api.education import router
from rkjo_api.education_dependencies import get_education_assessment_service, get_education_proof_service

TENANT = uuid4()
OWNER = uuid4()
FOREIGN = uuid4()


def client(*, assessment=None, proof=None):
    app = FastAPI()
    @app.middleware("http")
    async def identity(request, call_next):
        request.state.api_role = "viewer"
        request.state.api_tenant_id = str(TENANT)
        request.state.api_subject = str(OWNER)
        return await call_next(request)
    app.include_router(router)
    if assessment:
        app.dependency_overrides[get_education_assessment_service] = lambda: assessment
    if proof:
        app.dependency_overrides[get_education_proof_service] = lambda: proof
    return TestClient(app)


class Attempts:
    def __init__(self):
        self.calls = 0
    def start_attempt(self, **kwargs):
        self.calls += 1
        raise AssertionError("Must not start foreign attempt")


class Proof:
    def __init__(self):
        self.reads = 0
        self.submits = 0
    def get_challenge(self, **kwargs):
        self.reads += 1
        return type("Challenge", (), {"learner_id": FOREIGN})()
    def get_verification_question(self, **kwargs):
        raise AssertionError("Must not disclose foreign question")
    def submit(self, **kwargs):
        self.submits += 1
        raise AssertionError("Must not submit foreign proof")


def test_start_attempt_rejects_other_student():
    service = Attempts()
    response = client(assessment=service).post("/education/attempts",
        headers={"Authorization": "Bearer test"},
        json={"assessment_id": str(uuid4()), "learner_id": str(FOREIGN)})
    assert response.status_code == 403
    assert service.calls == 0


def test_foreign_proof_prompt_hidden():
    service = Proof()
    response = client(proof=service).get(
        "/education/proof-challenges/" + str(uuid4()),
        headers={"Authorization": "Bearer test"})
    assert response.status_code == 404
    assert service.reads == 1


def test_foreign_proof_cannot_be_submitted():
    service = Proof()
    response = client(proof=service).post(
        "/education/proof-challenges/" + str(uuid4()) + "/submit",
        headers={"Authorization": "Bearer test"}, json={"answer": "4"})
    assert response.status_code == 404
    assert service.submits == 0
