from uuid import uuid4

import pytest

from rkjo_education.assessment.models import (
    Attempt,
    AttemptAnswerEvidence,
)
from rkjo_education.policy import AssistanceLevel


def test_attempt_records_question_evidence():
    question_id = uuid4()
    attempt = Attempt(
        tenant_id=uuid4(),
        assessment_id=uuid4(),
        learner_id=uuid4(),
    )

    attempt.answer(
        question_id,
        "42",
        evidence=AttemptAnswerEvidence(
            assistance_level=AssistanceLevel.STRONG_HINT,
            hints_used=2,
            attempt_count=3,
            response_time_seconds=45,
        ),
    )

    assert attempt.answers[question_id] == "42"

    evidence = attempt.evidence[question_id]
    assert evidence.assistance_level == AssistanceLevel.STRONG_HINT
    assert evidence.hints_used == 2
    assert evidence.attempt_count == 3
    assert evidence.response_time_seconds == 45


def test_attempt_remains_backward_compatible_without_evidence():
    question_id = uuid4()
    attempt = Attempt(
        tenant_id=uuid4(),
        assessment_id=uuid4(),
        learner_id=uuid4(),
    )

    attempt.answer(question_id, "Paris")

    assert attempt.answers[question_id] == "Paris"
    assert question_id not in attempt.evidence


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"hints_used": -1}, "hints_used"),
        ({"attempt_count": 0}, "attempt_count"),
        ({"response_time_seconds": -1}, "response_time_seconds"),
    ],
)
def test_attempt_evidence_rejects_invalid_metrics(kwargs, message):
    with pytest.raises(ValueError, match=message):
        AttemptAnswerEvidence(**kwargs)


def test_submit_rejects_evidence_without_matching_answer():
    from rkjo_education.assessment.models import Assessment, Question
    from rkjo_education.assessment.repository import InMemoryAssessmentRepository
    from rkjo_education.assessment.service import AssessmentService

    tenant_id = uuid4()
    course_id = uuid4()
    learner_id = uuid4()

    repository = InMemoryAssessmentRepository()
    service = AssessmentService(repository)

    assessment = Assessment(
        tenant_id=tenant_id,
        course_id=course_id,
        title="Evidence validation",
    )
    question = Question(
        tenant_id=tenant_id,
        prompt="2 + 2 ?",
        correct_answer="4",
    )
    assessment.add_question(question)
    repository.save_assessment(assessment)

    attempt = service.start_attempt(
        tenant_id=tenant_id,
        assessment_id=assessment.id,
        learner_id=learner_id,
    )

    with pytest.raises(
        ValueError,
        match="evidence must reference a submitted answer",
    ):
        service.submit_attempt(
            tenant_id=tenant_id,
            attempt_id=attempt.id,
            answers={},
            evidence={
                question.id: AttemptAnswerEvidence(
                    assistance_level=AssistanceLevel.LIGHT_HINT,
                )
            },
        )


def test_submit_rejects_answer_for_unknown_question():
    from rkjo_education.assessment.models import Assessment, Question
    from rkjo_education.assessment.repository import InMemoryAssessmentRepository
    from rkjo_education.assessment.service import AssessmentService

    tenant_id = uuid4()

    repository = InMemoryAssessmentRepository()
    service = AssessmentService(repository)

    assessment = Assessment(
        tenant_id=tenant_id,
        course_id=uuid4(),
        title="Question validation",
    )
    assessment.add_question(
        Question(
            tenant_id=tenant_id,
            prompt="2 + 2 ?",
            correct_answer="4",
        )
    )
    repository.save_assessment(assessment)

    attempt = service.start_attempt(
        tenant_id=tenant_id,
        assessment_id=assessment.id,
        learner_id=uuid4(),
    )

    with pytest.raises(
        ValueError,
        match="answer must reference an assessment question",
    ):
        service.submit_attempt(
            tenant_id=tenant_id,
            attempt_id=attempt.id,
            answers={uuid4(): "4"},
        )
