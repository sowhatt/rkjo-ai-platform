"""Submitting a question must never mutate a foreign learner's attempt."""
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from rkjo_api.education import router
from rkjo_api.education_dependencies import (
    get_education_assessment_learning_service,
    get_education_assessment_service,
)

TENANT = uuid4()
LEARNER = uuid4()


class AttemptReader:
    def get_attempt(self, **kwargs):
        return type("Attempt", (), {"learner_id": uuid4()})()


class RecordingSubmission:
    def __init__(self):
        self.calls = 0

    def submit_attempt(self, **kwargs):
        self.calls += 1
        raise AssertionError("submission must never run")


def test_foreign_attempt_submission_rejected_before_grading():
    app = FastAPI()
    @app.middleware("http")
    async def verified_identity(request, call_next):
        request.state.api_role = "viewer"
        request.state.api_tenant_id = str(TENANT)
        request.state.api_subject = str(LEARNER)
        return await call_next(request)
    app.include_router(router)
    writer = RecordingSubmission()
    app.dependency_overrides[get_education_assessment_service] = AttemptReader
    app.dependency_overrides[get_education_assessment_learning_service] = lambda: writer
    response = TestClient(app).post(
        "/education/attempts/" + str(uuid4()) + "/submit",
        headers={"Authorization": "Bearer test"},
        json={"answers": {}},
    )
    assert response.status_code == 404
    assert writer.calls == 0
