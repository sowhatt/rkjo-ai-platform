import pytest

from rkjo_education.tutor.guided_lesson import (
    GuidedLesson,
    LessonPhase,
    advance_lesson,
    request_hint,
    submit_proof,
)


def test_guided_session_requires_comprehension_check_and_autonomous_proof():
    session = GuidedLesson(learner_id="student-1", objective="Addition")
    session = advance_lesson(session)
    assert session.phase == LessonPhase.CHECK
    with pytest.raises(ValueError):
        advance_lesson(session)
    assert advance_lesson(session, understood=False).phase == LessonPhase.EXPLAIN
    session = advance_lesson(session, understood=True)
    session = request_hint(session)
    assert session.hints_used == 1
    session = advance_lesson(session)
    assert session.phase == LessonPhase.PROOF
    with pytest.raises(ValueError):
        submit_proof(session, correct=True, assisted=True)
    session = submit_proof(session, correct=True)
    assert session.phase == LessonPhase.REVIEW
    assert session.autonomous_proof_passed


def test_hint_not_allowed_during_proof():
    session = GuidedLesson("student-1", "Addition", phase=LessonPhase.PROOF)
    with pytest.raises(ValueError):
        request_hint(session)
