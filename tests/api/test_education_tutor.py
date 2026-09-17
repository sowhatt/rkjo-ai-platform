from dataclasses import dataclass
from uuid import uuid4

from rkjo_api.education_dependencies import get_education_tutor_service
from rkjo_api.main import app
from rkjo_education.tutor.models import TutorAnswer, TutorSource


@dataclass
class FakeTutorService:
    def ask(self, *, tenant_id, learner_id, course_id, question):
        return TutorAnswer(
            learner_id=learner_id,
            course_id=course_id,
            answer="Une fraction est une partie d'un tout.",
            adapted_question=question,
            level="CE2",
            completion_percent=45,
            weak_competencies=["MATH.FRACTION"],
            sources=[
                TutorSource(
                    citation=1,
                    document_id="doc-1",
                    chunk_id="chunk-1",
                    score=0.91,
                )
            ],
        )


def test_tutor_api_returns_adaptive_grounded_answer(client, monkeypatch):
    tenant_id = uuid4()
    learner_id = uuid4()
    course_id = uuid4()
    monkeypatch.setenv("RKJO_OPERATOR_TENANT_ID", str(tenant_id))
    app.dependency_overrides[get_education_tutor_service] = lambda: FakeTutorService()
    try:
        response = client.post(
            "/education/tutor/ask",
            headers={"X-API-Key": "rkjo-operator-key"},
            json={
                "learner_id": str(learner_id),
                "course_id": str(course_id),
                "question": "Explique-moi les fractions",
            },
        )
    finally:
        app.dependency_overrides.pop(get_education_tutor_service, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["level"] == "CE2"
    assert payload["completion_percent"] == 45
    assert payload["weak_competencies"] == ["MATH.FRACTION"]
    assert payload["sources"][0]["document_id"] == "doc-1"
