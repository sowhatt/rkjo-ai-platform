import os
from uuid import uuid4

from rkjo_education.assessment.postgres_repository import PostgresAssessmentRepository
from rkjo_education.assessment.service import AssessmentService


def database_url() -> str:
    return os.environ["RKJO_DATABASE_URL"]


def test_assessment_postgres_roundtrip():
    tenant_id = uuid4()
    repository = PostgresAssessmentRepository(database_url())
    service = AssessmentService(repository)

    assessment = service.create_assessment(
        tenant_id=tenant_id,
        course_id=uuid4(),
        title="Lecture",
        questions=[
            {
                "prompt": "Mot correct ?",
                "correct_answer": "chat",
                "points": 2,
                "competency_code": "FR.READ",
            }
        ],
    )
    restored = service.get_assessment(
        tenant_id=tenant_id,
        assessment_id=assessment.id,
    )
    attempt = service.start_attempt(
        tenant_id=tenant_id,
        assessment_id=assessment.id,
        learner_id=uuid4(),
    )
    submitted = service.submit_attempt(
        tenant_id=tenant_id,
        attempt_id=attempt.id,
        answers={restored.questions[0].id: "CHAT"},
    )
    persisted_attempt = repository.get_attempt(
        tenant_id=tenant_id,
        attempt_id=attempt.id,
    )

    assert restored.title == "Lecture"
    assert restored.questions[0].competency_code == "FR.READ"
    assert submitted.score == 2
    assert submitted.percentage == 100
    assert persisted_attempt is not None
    assert persisted_attempt.status.value == "submitted"
