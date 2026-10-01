from uuid import uuid4

from rkjo_education.events import EducationEventType, EducationLearningEvent
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


def test_nba_counts_consecutive_failures_until_success():
    tenant_id = uuid4()
    learner_id = uuid4()
    competency = "MATH.ADD"
    events = [
        EducationLearningEvent(
            event_type=EducationEventType.ANSWER_SUBMITTED,
            tenant_id=tenant_id,
            learner_id=learner_id,
            competency_code=competency,
            payload={"correct": True},
        ),
        EducationLearningEvent(
            event_type=EducationEventType.ANSWER_SUBMITTED,
            tenant_id=tenant_id,
            learner_id=learner_id,
            competency_code=competency,
            payload={"correct": False},
        ),
        EducationLearningEvent(
            event_type=EducationEventType.ANSWER_SUBMITTED,
            tenant_id=tenant_id,
            learner_id=learner_id,
            competency_code=competency,
            payload={"correct": False},
        ),
    ]
    assert NextBestActionService.repeated_failures(
        events,
        competency_code=competency,
    ) == 2
