from rkjo_education.intelligence.next_best_action import (
    NextBestActionService,
    NextBestActionType,
)


def test_nba_moves_forward_after_autonomous_success():
    decision = NextBestActionService().decide(
        correct=True,
        autonomy_score=100,
        mastery="mastered",
        proof_required=False,
    )
    assert decision.action == NextBestActionType.NEXT_ACTIVITY


def test_nba_requests_proof_after_assisted_success():
    decision = NextBestActionService().decide(
        correct=True,
        autonomy_score=50,
        mastery="developing",
        proof_required=True,
    )
    assert decision.action == NextBestActionType.REQUEST_PROOF


def test_nba_assigns_consolidation_after_failure():
    decision = NextBestActionService().decide(
        correct=False,
        autonomy_score=0,
        mastery="not_demonstrated",
        proof_required=False,
    )
    assert decision.action == NextBestActionType.CONSOLIDATION


def test_nba_escalates_repeated_failures():
    decision = NextBestActionService().decide(
        correct=False,
        autonomy_score=0,
        mastery="not_demonstrated",
        proof_required=False,
        repeated_failures=2,
    )
    assert decision.action == NextBestActionType.CONSOLIDATION_AND_ALERT
