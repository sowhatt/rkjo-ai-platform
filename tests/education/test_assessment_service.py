from uuid import uuid4

import pytest

from rkjo_education.assessment.repository import InMemoryAssessmentRepository
from rkjo_education.assessment.service import AssessmentService


def test_assessment_attempt_scores_answers():
    tenant_id = uuid4()
    service = AssessmentService(InMemoryAssessmentRepository())
    assessment = service.create_assessment(
        tenant_id=tenant_id,
        course_id=uuid4(),
        title="Addition",
        questions=[
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
    )
    attempt = service.start_attempt(
        tenant_id=tenant_id,
        assessment_id=assessment.id,
        learner_id=uuid4(),
    )

    submitted = service.submit_attempt(
        tenant_id=tenant_id,
        attempt_id=attempt.id,
        answers={
            assessment.questions[0].id: "4",
            assessment.questions[1].id: "5",
        },
    )

    assert submitted.score == 2
    assert submitted.max_score == 3
    assert submitted.percentage == 67
    assert submitted.status.value == "submitted"


def test_submitted_attempt_cannot_be_submitted_twice():
    tenant_id = uuid4()
    service = AssessmentService(InMemoryAssessmentRepository())
    assessment = service.create_assessment(
        tenant_id=tenant_id,
        course_id=uuid4(),
        title="Quiz",
        questions=[{"prompt": "A?", "correct_answer": "B"}],
    )
    attempt = service.start_attempt(
        tenant_id=tenant_id,
        assessment_id=assessment.id,
        learner_id=uuid4(),
    )
    service.submit_attempt(
        tenant_id=tenant_id,
        attempt_id=attempt.id,
        answers={assessment.questions[0].id: "B"},
    )

    with pytest.raises(ValueError, match="submitted attempt"):
        service.submit_attempt(
            tenant_id=tenant_id,
            attempt_id=attempt.id,
            answers={assessment.questions[0].id: "B"},
        )


def test_course_completion_counts_finished_assessments_not_scores():
    tenant_id = uuid4()
    learner_id = uuid4()
    course_id = uuid4()
    service = AssessmentService(InMemoryAssessmentRepository())

    assessments = [
        service.create_assessment(
            tenant_id=tenant_id,
            course_id=course_id,
            title=f"Activity {index}",
            questions=[{"prompt": "2 + 2 ?", "correct_answer": "4"}],
        )
        for index in (1, 2)
    ]

    assert service.course_completion_percent(
        tenant_id=tenant_id,
        learner_id=learner_id,
        course_id=course_id,
    ) == 0

    attempt = service.start_attempt(
        tenant_id=tenant_id,
        assessment_id=assessments[0].id,
        learner_id=learner_id,
    )
    service.submit_attempt(
        tenant_id=tenant_id,
        attempt_id=attempt.id,
        answers={assessments[0].questions[0].id: "wrong"},
    )

    assert service.course_completion_percent(
        tenant_id=tenant_id,
        learner_id=learner_id,
        course_id=course_id,
    ) == 50
