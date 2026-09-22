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


def test_attempt_evidence_postgres_roundtrip():
    from rkjo_education.assessment.models import AttemptAnswerEvidence
    from rkjo_education.policy import AssistanceLevel

    tenant_id = uuid4()
    repository = PostgresAssessmentRepository(database_url())
    service = AssessmentService(repository)

    assessment = service.create_assessment(
        tenant_id=tenant_id,
        course_id=uuid4(),
        title="Fractions",
        questions=[
            {
                "prompt": "1/2 + 1/2 ?",
                "correct_answer": "1",
                "competency_code": "MATH.FRACTION",
            }
        ],
    )

    attempt = service.start_attempt(
        tenant_id=tenant_id,
        assessment_id=assessment.id,
        learner_id=uuid4(),
    )

    question_id = assessment.questions[0].id
    attempt.answer(
        question_id,
        "1",
        evidence=AttemptAnswerEvidence(
            assistance_level=AssistanceLevel.LIGHT_HINT,
            hints_used=1,
            attempt_count=2,
            response_time_seconds=37,
        ),
    )
    repository.save_attempt(attempt)

    restored = repository.get_attempt(
        tenant_id=tenant_id,
        attempt_id=attempt.id,
    )

    assert restored is not None
    assert restored.answers[question_id] == "1"

    evidence = restored.evidence[question_id]
    assert evidence.assistance_level == AssistanceLevel.LIGHT_HINT
    assert evidence.hints_used == 1
    assert evidence.attempt_count == 2
    assert evidence.response_time_seconds == 37
