"""Read-only NBA route: individual learner binding and trusted injected service."""
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from rkjo_api.education import router
from rkjo_api.education_dependencies import get_education_assessment_action_service
from rkjo_education.learning.assessment_action_service import EvidenceNotFoundError
from rkjo_education.learning.next_action_policy import (
    ActionDecision, NextAction,
)


TENANT = uuid4()
LEARNER = uuid4()
ATTEMPT = uuid4()
QUESTION = uuid4()


class FakeActionService:
    def __init__(self, *, not_found=False):
        self.calls = []
        self.not_found = not_found

    def recommend(self, **kwargs):
        self.calls.append(kwargs)
        if self.not_found:
            raise EvidenceNotFoundError("missing")
        return ActionDecision(NextAction.AUTONOMOUS_PROOF, "Proof required")


def client(*, subject=LEARNER, service=None):
    app = FastAPI()

    @app.middleware("http")
    async def identity(request, call_next):
        if request.headers.get("authorization") == "Bearer test-identity":
            request.state.api_role = "viewer"
            request.state.api_subject = str(subject)
            request.state.api_tenant_id = str(TENANT)
        return await call_next(request)

    app.include_router(router)
    provider = service or FakeActionService()
    app.dependency_overrides[get_education_assessment_action_service] = lambda: provider
    return TestClient(app), provider


def url():
    return f"/education/attempts/{ATTEMPT}/questions/{QUESTION}/next-action"


def test_valid_subject_uses_only_server_identity():
    http, service = client()
    response = http.get(url(), headers={"Authorization": "Bearer test-identity"})
    assert response.status_code == 200
    assert response.json()["action"] == "autonomous_proof"
    assert service.calls == [{
        "tenant_id": TENANT,
        "learner_id": LEARNER,
        "attempt_id": ATTEMPT,
        "question_id": QUESTION,
        "proof_challenge_id": None,
    }]


def test_rejects_api_key_or_missing_individual_identity():
    http, service = client()
    response = http.get(url())
    assert response.status_code in (401, 403)
    assert service.calls == []


def test_rejects_unbound_subject():
    http, service = client(subject="not-a-uuid")
    response = http.get(url(), headers={"Authorization": "Bearer test-identity"})
    assert response.status_code == 403
    assert service.calls == []


def test_does_not_accept_browser_claimed_mastery():
    http, service = client()
    response = http.get(url() + "?score=100&autonomous_proof_passed=true&missing_prerequisites=false",
                        headers={"Authorization": "Bearer test-identity"})
    assert response.status_code == 200
    assert service.calls[0].get("autonomous_proof_passed") is None


def test_missing_evidence_is_404():
    service = FakeActionService(not_found=True)
    http, _ = client(service=service)
    response = http.get(url(), headers={"Authorization": "Bearer test-identity"})
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
