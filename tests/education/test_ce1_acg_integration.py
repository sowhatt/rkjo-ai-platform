import pytest

from rkjo_education.learning.ce1_orchestrator import (
    TurnKind, new_session, transition,
)
from rkjo_education.learning.next_action_policy import NextAction
from rkjo_education.tutor.guided_lesson import LessonPhase


def run(session, kind, answer=None):
    return transition(session, kind, answer=answer)


def test_full_ce1_guided_then_independent_even_after_hint():
    session = new_session("learner-test")
    result = run(session, TurnKind.START)
    assert result.session.lesson.phase == LessonPhase.CHECK
    assert result.routing_plan.verifier == "sympy"

    result = run(result.session, TurnKind.UNDERSTOOD)
    assert result.session.lesson.phase == LessonPhase.PRACTICE
    result = run(result.session, TurnKind.HINT)
    assert result.session.lesson.hints_used == 1

    result = run(result.session, TurnKind.ANSWER, answer=13)
    assert result.session.lesson.phase == LessonPhase.PROOF
    assert result.next_action.action == NextAction.AUTONOMOUS_PROOF

    result = run(result.session, TurnKind.ANSWER, answer=13)
    assert result.session.lesson.phase == LessonPhase.REVIEW
    assert result.session.lesson.autonomous_proof_passed
    assert result.next_action.action == NextAction.ADVANCE


def test_incorrect_guided_answer_does_not_start_proof():
    s = run(new_session("learner"), TurnKind.START).session
    s = run(s, TurnKind.UNDERSTOOD).session
    r = run(s, TurnKind.ANSWER, answer=12)
    assert r.session.lesson.phase == LessonPhase.PRACTICE
    assert not r.session.guided_correct
    assert r.next_action.action == NextAction.PRACTICE


def test_incorrect_independent_proof_does_not_advance():
    s = run(new_session("learner"), TurnKind.START).session
    s = run(s, TurnKind.UNDERSTOOD).session
    s = run(s, TurnKind.ANSWER, answer=13).session
    r = run(s, TurnKind.ANSWER, answer=12)
    assert r.session.lesson.phase == LessonPhase.REVIEW
    assert not r.session.lesson.autonomous_proof_passed
    assert r.next_action.action == NextAction.PRACTICE


def test_needs_another_explanation_requires_comprehension_again():
    s = run(new_session("learner"), TurnKind.START).session
    r = run(s, TurnKind.NEED_EXPLANATION)
    assert r.session.lesson.phase == LessonPhase.CHECK
    assert r.session.additional_explanations == 1


def test_proof_refuses_hint_or_reformulation():
    s = run(new_session("learner"), TurnKind.START).session
    s = run(s, TurnKind.UNDERSTOOD).session
    s = run(s, TurnKind.ANSWER, answer=13).session
    with pytest.raises(ValueError):
        run(s, TurnKind.HINT)
    with pytest.raises(ValueError):
        run(s, TurnKind.NEED_EXPLANATION)


@pytest.mark.parametrize("invalid", [None, -1, True, 13.0, "13"])
def test_rejects_non_integer_or_negative_answers(invalid):
    s = run(new_session("learner"), TurnKind.START).session
    s = run(s, TurnKind.UNDERSTOOD).session
    with pytest.raises(ValueError):
        run(s, TurnKind.ANSWER, answer=invalid)


def test_rejects_empty_learner():
    with pytest.raises(ValueError):
        new_session(" ")
