from uuid import uuid4

from rkjo_education.events import EducationEventType, EducationLearningEvent
from rkjo_education.intelligence.next_best_action import (
    CompetencySignal,
    NBAContext,
    NBA_POLICY_VERSION,
    NBAPolicyConfig,
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


def sig(**overrides):
    values = dict(
        competency_code="MATH.ADD",
        mastery=.60,
        autonomy=.90,
        retention=.90,
        latest_correct=True,
    )
    values.update(overrides)
    return CompetencySignal(**values)


def decide(*signals, target="MATH.ADD", **context):
    return NextBestActionService().decide_context(
        NBAContext(competencies=tuple(signals), target_competency=target, **context)
    )


def test_t01_new_student_positioning():
    d = decide()
    assert (d.action, d.rule_id) == (NextBestActionType.POSITIONING_TEST, "R0")


def test_t02_prerequisite_beats_first_failure():
    d = decide(sig(mastery=.30, latest_correct=False, prerequisite_code="MATH.NUM", prerequisite_mastery=.35))
    assert (d.action, d.rule_id, d.target_competency) == (NextBestActionType.PRACTICE_PREREQUISITE, "R3", "MATH.NUM")


def test_t03_first_failure_remediates():
    d = decide(sig(mastery=.55, latest_correct=False, prerequisite_code="MATH.NUM", prerequisite_mastery=.60))
    assert (d.action, d.rule_id) == (NextBestActionType.REMEDIATE, "R5")


def test_t04_two_failures_reexplain():
    d = decide(sig(latest_correct=False, consecutive_failures=2))
    assert (d.action, d.rule_id, d.signals["difficulty_delta"]) == (NextBestActionType.REEXPLAIN_DIFFERENTLY, "R4", -1)


def test_t05_antiloop_beats_prerequisite():
    d = decide(sig(mastery=.37, latest_correct=False, prerequisite_code="MATH.NUM", prerequisite_mastery=.30, remediation_count=3, remediation_mastery_gain=.02))
    assert (d.action, d.rule_id, d.secondary_action) == (NextBestActionType.MARK_FOR_REVIEW, "R1", NextBestActionType.ASK_FOR_HUMAN_HELP)


def test_t06_assisted_success_practice_similar():
    d = decide(sig(latest_help=.5, autonomy=.55))
    assert (d.action, d.rule_id) == (NextBestActionType.PRACTICE_SIMILAR, "R7")


def test_t07_three_autonomous_successes_request_proof():
    d = decide(sig(consecutive_no_hint_successes=3, distinct_success_exercises=3))
    assert (d.action, d.rule_id) == (NextBestActionType.REQUEST_PROOF, "R8")


def test_t08_failed_proof_remediates():
    d = decide(sig(mastery=.75, latest_proof="failed"))
    assert (d.action, d.rule_id) == (NextBestActionType.REMEDIATE, "R2")


def test_t09_passed_proof_advances_to_next_eligible_competency():
    d = decide(
        sig(mastery=.80, latest_proof="passed", valid_proof=True),
        sig(competency_code="MATH.SUB", latest_correct=None),
    )
    assert (d.action, d.rule_id, d.target_competency) == (
        NextBestActionType.ADVANCE,
        "R9",
        "MATH.SUB",
    )


def test_t10_retention_review_beats_advance():
    d = decide(
        sig(mastery=.80, latest_proof="passed", valid_proof=True),
        sig(competency_code="MATH.SUB", mastery=.65, retention=.50, importance=3),
    )
    assert (d.action, d.rule_id, d.target_competency) == (NextBestActionType.REVIEW, "R6", "MATH.SUB")


def test_t11_autonomous_success_increases_difficulty():
    d = decide(sig())
    assert (d.action, d.rule_id) == (NextBestActionType.INCREASE_DIFFICULTY, "R10")


def test_t12_exam_m1_turns_r7_into_timed_practice():
    d = decide(sig(latest_help=.5, autonomy=.55), exam_days_remaining=10, tester_share_last_24h=.20)
    assert (d.action, d.rule_id, d.modifiers) == (NextBestActionType.PRACTICE_TIMED, "R7", ("M1",))


def test_t13_failed_corrected_copy_remediates_without_autonomy_signal():
    d = decide(sig(
        mastery=.35,
        autonomy=1.0,
        latest_correct=None,
        latest_observation_failed=True,
    ))
    assert (d.action, d.rule_id) == (NextBestActionType.REMEDIATE, "R5")

def test_t14_exam_m2_starts_mock_before_review():
    d = decide(sig(retention=.50), exam_days_remaining=2, mock_exam_last_24h=False)
    assert d.action == NextBestActionType.START_MOCK_EXAM
    assert d.rule_id == "R6"
    assert d.modifiers == ("M2",)


def test_m2_excludes_unseen_or_out_of_exam_competencies():
    d = decide(
        sig(competency_code="MATH.ADD", covered_by_exam=False),
        sig(competency_code="MATH.SUB", covered_by_exam=True, retention=.50),
        target="MATH.ADD",
        exam_days_remaining=2,
        mock_exam_last_24h=True,
    )
    assert d.target_competency == "MATH.SUB"


def test_m2_prerequisite_requires_high_prerequisite_importance():
    d = decide(sig(
        mastery=.30,
        latest_correct=False,
        prerequisite_code="MATH.NUM",
        prerequisite_mastery=.30,
        prerequisite_importance=1,
    ), exam_days_remaining=2, mock_exam_last_24h=True)
    assert d.rule_id == "R5"
    assert d.action == NextBestActionType.REMEDIATE


def test_t15_decision_is_explainable_and_versioned():
    d = decide(sig(latest_correct=False))
    assert d.rule_id
    assert d.signals
    assert d.policy_version == NBA_POLICY_VERSION
    assert d.explanation
    assert d.timestamp.tzinfo is not None


def test_r0_is_explainable_even_without_observations():
    d = decide()
    assert d.rule_id == "R0"
    assert d.signals == {"observation_count": 0}
    assert d.explanation


def test_policy_thresholds_and_version_are_configurable():
    service = NextBestActionService(NBAPolicyConfig(
        policy_version="pilot-2026-10",
        autonomy_low=.80,
    ))
    d = service.decide_context(NBAContext(
        competencies=(sig(autonomy=.75, latest_help=0),),
        target_competency="MATH.ADD",
    ))
    assert (d.action, d.rule_id) == (NextBestActionType.PRACTICE_SIMILAR, "R7")
    assert d.policy_version == "pilot-2026-10"
