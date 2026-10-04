from rkjo_education.intelligence.corrected_copy import (
    CorrectedCopyEvidenceService,
    CorrectedQuestionEvidence,
)
from rkjo_education.intelligence.mastery import LearnerModelCalculator, LearnerObservation
from rkjo_education.intelligence.next_best_action import (
    CompetencySignal,
    NBAContext,
    NextBestActionService,
    NextBestActionType,
)


def test_t13_corrected_copy_updates_mastery_not_autonomy_and_remediates():
    calculator = LearnerModelCalculator()
    before = calculator.calculate(
        observations=[LearnerObservation(score=1.0, weight=1.0)],
        help_levels=[0.0],
        days_since_success=0,
        successful_proof=False,
    )
    corrected = CorrectedQuestionEvidence(
        competency_code="MATH.ADD",
        earned_points=0,
        max_points=4,
        alignment_confidence=.85,
    )
    observations = CorrectedCopyEvidenceService.observations([corrected])["MATH.ADD"]
    after = calculator.calculate(
        observations=[LearnerObservation(score=1.0, weight=1.0), *observations],
        help_levels=[0.0],
        days_since_success=0,
        successful_proof=False,
    )
    assert after.mastery < before.mastery
    assert after.autonomy == before.autonomy

    decision = NextBestActionService().decide_context(
        NBAContext(
            competencies=(
                CompetencySignal(
                    competency_code="MATH.ADD",
                    mastery=after.mastery,
                    autonomy=after.autonomy,
                    latest_correct=False,
                ),
            ),
            target_competency="MATH.ADD",
        )
    )
    assert (decision.action, decision.rule_id) == (
        NextBestActionType.REMEDIATE,
        "R5",
    )


def test_low_confidence_corrected_copy_requires_student_confirmation():
    corrected = CorrectedQuestionEvidence(
        competency_code="MATH.ADD",
        earned_points=2,
        max_points=4,
        alignment_confidence=.69,
    )
    assert CorrectedCopyEvidenceService.observations([corrected]) == {}
    accepted = CorrectedCopyEvidenceService.observations(
        [corrected],
        confirmed_competencies={"MATH.ADD"},
    )
    assert accepted["MATH.ADD"][0].score == .5


def test_corrected_copy_is_split_question_by_question():
    questions = [
        CorrectedQuestionEvidence("MATH.ADD", 4, 4, .9),
        CorrectedQuestionEvidence("MATH.ADD", 0, 4, .9),
        CorrectedQuestionEvidence("MATH.SUB", 2, 4, .9),
    ]
    evidence = CorrectedCopyEvidenceService.observations(questions)
    assert [item.score for item in evidence["MATH.ADD"]] == [1.0, 0.0]
    assert [item.score for item in evidence["MATH.SUB"]] == [.5]
