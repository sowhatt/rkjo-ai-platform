import pytest

from rkjo_education.learning.next_action_policy import (
    LearningSignals,
    NextAction,
    recommend_next_action,
)


@pytest.mark.parametrize(
    ("signals", "expected"),
    [
        (LearningSignals(assessed=False), NextAction.DIAGNOSE),
        (LearningSignals(assessed=True, last_answer_correct=False), NextAction.PRACTICE),
        (LearningSignals(assessed=True, last_answer_correct=True, hints_used=2), NextAction.AUTONOMOUS_PROOF),
        (LearningSignals(assessed=True, last_answer_correct=True, autonomous_proof_passed=True), NextAction.ADVANCE),
        (LearningSignals(assessed=True, last_answer_correct=True, missing_prerequisites=True), NextAction.REMEDIATE),
    ],
)
def test_next_action_policy(signals, expected):
    decision = recommend_next_action(signals)
    assert decision.action == expected
    assert decision.reason


def test_rejects_invalid_hint_count():
    with pytest.raises(ValueError):
        recommend_next_action(LearningSignals(assessed=True, hints_used=-1))
