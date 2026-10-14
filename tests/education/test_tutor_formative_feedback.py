"""Tutor feedback: identity binding, question ownership, no grading."""
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from rkjo_api.education_tutor import router
from rkjo_api.education_dependencies import (
    get_education_assessment_service,
    get_education_tutor_service,
)
from rkjo_api.security import ApiRole, required_role_for_request

TENANT = uuid4()
LEARNER = uuid4()
COURSE = uuid4()
ASSESSMENT = uuid4()
QUESTION = uuid4()


class AssessmentServiceFake:
    def __init__(self, course_id=COURSE):
        self.course_id = course_id

    def get_assessment(self, **kwargs):
        assert kwargs["tenant_id"] == TENANT
        assert kwargs["assessment_id"] == ASSESSMENT
        return SimpleNamespace(
            course_id=self.course_id,
            questions=[SimpleNamespace(id=QUESTION, prompt="Explique les unités et dizaines")],
        )


class TutorFake:
    def __init__(self):
        self.calls = []

    def ask(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(answer="Relis l'exemple à la page 2.", sources=[])


def make_client(assessments, tutor):
    app = FastAPI()

    @app.middleware("http")
    async def identity(request, call_next):
        # Mirror the authenticated request state supplied by the real
        # middleware; this unit test does not verify JWT signatures.
        if request.headers.get("authorization") == "Bearer test":
            request.state.api_role = "viewer"
            request.state.api_tenant_id = str(TENANT)
            request.state.api_subject = str(LEARNER)
        return await call_next(request)

    app.include_router(router)
    app.dependency_overrides[get_education_assessment_service] = lambda: assessments
    app.dependency_overrides[get_education_tutor_service] = lambda: tutor
    return TestClient(app)


def body(**kw):
    return {
        "course_id": str(COURSE),
        "assessment_id": str(ASSESSMENT),
        "question_id": str(QUESTION),
        "student_answer": "Les unités sont à droite.",
        **kw,
    }


def test_feedback_requires_individual_bearer():
    tutor = TutorFake()
    r = make_client(AssessmentServiceFake(), tutor).post("/education/tutor/feedback", json=body())
    assert r.status_code == 403
    assert tutor.calls == []


def test_feedback_rejects_mismatched_course_before_tutor():
    tutor = TutorFake()
    r = make_client(AssessmentServiceFake(course_id=uuid4()), tutor).post(
        "/education/tutor/feedback", json=body(),
        headers={"Authorization": "Bearer test"},
    )
    assert r.status_code == 404
    assert tutor.calls == []


def test_feedback_rejects_unknown_question_before_tutor():
    tutor = TutorFake()
    r = make_client(AssessmentServiceFake(), tutor).post(
        "/education/tutor/feedback", json=body(question_id=str(uuid4())),
        headers={"Authorization": "Bearer test"},
    )
    assert r.status_code == 404
    assert tutor.calls == []


def test_feedback_uses_server_identity_and_never_grades():
    tutor = TutorFake()
    r = make_client(AssessmentServiceFake(), tutor).post(
        "/education/tutor/feedback", json=body(),
        headers={"Authorization": "Bearer test"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["graded"] is False
    assert r.json()["mastery_updated"] is False
    assert tutor.calls[0]["tenant_id"] == TENANT
    assert tutor.calls[0]["learner_id"] == LEARNER
    assert tutor.calls[0]["course_id"] == COURSE


def test_feedback_is_viewer_but_legacy_tutor_is_operator():
    assert required_role_for_request(method="POST", path="/education/tutor/feedback") == ApiRole.VIEWER
    assert required_role_for_request(method="POST", path="/education/tutor/ask") == ApiRole.OPERATOR
