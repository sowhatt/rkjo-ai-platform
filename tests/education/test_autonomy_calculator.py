from rkjo_education.assessment.models import AttemptAnswerEvidence
from rkjo_education.intelligence import AutonomyCalculator, AutonomyEvidence
from rkjo_education.policy import AssistanceLevel


def test_correct_without_help_is_fully_autonomous():
    result = AutonomyCalculator().calculate(
        AutonomyEvidence(
            correct=True,
            assistance_level=AssistanceLevel.NONE,
            hints_used=0,
            attempt_count=1,
        )
    )

    assert result.score == 100
    assert result.independently_correct is True
    assert result.requires_independent_verification is False


def test_light_hint_reduces_autonomy():
    result = AutonomyCalculator().calculate(
        AutonomyEvidence(
            correct=True,
            assistance_level=AssistanceLevel.LIGHT_HINT,
            hints_used=1,
            attempt_count=1,
        )
    )

    assert result.score == 70
    assert result.independently_correct is False
    assert result.requires_independent_verification is False


def test_extra_attempts_reduce_autonomy():
    result = AutonomyCalculator().calculate(
        AutonomyEvidence(
            correct=True,
            assistance_level=AssistanceLevel.NONE,
            hints_used=0,
            attempt_count=3,
        )
    )

    assert result.score == 90
    assert result.independently_correct is False


def test_strong_hint_requires_independent_verification():
    result = AutonomyCalculator().calculate(
        AutonomyEvidence(
            correct=True,
            assistance_level=AssistanceLevel.STRONG_HINT,
            hints_used=1,
            attempt_count=1,
        )
    )

    assert result.score == 50
    assert result.requires_independent_verification is True


def test_guided_method_requires_independent_verification():
    result = AutonomyCalculator().calculate(
        AutonomyEvidence(
            correct=True,
            assistance_level=AssistanceLevel.GUIDED_METHOD,
            hints_used=0,
            attempt_count=1,
        )
    )

    assert result.score == 30
    assert result.requires_independent_verification is True


def test_explained_solution_is_not_autonomous_success():
    result = AutonomyCalculator().calculate(
        AutonomyEvidence(
            correct=True,
            assistance_level=AssistanceLevel.EXPLAINED_SOLUTION,
            hints_used=0,
            attempt_count=1,
        )
    )

    assert result.score == 0
    assert result.independently_correct is False
    assert result.requires_independent_verification is True


def test_wrong_answer_has_no_positive_autonomy_evidence():
    result = AutonomyCalculator().calculate(
        AutonomyEvidence(
            correct=False,
            assistance_level=AssistanceLevel.NONE,
            hints_used=0,
            attempt_count=1,
        )
    )

    assert result.score == 0
    assert result.independently_correct is False


def test_response_time_does_not_penalize_autonomy():
    calculator = AutonomyCalculator()

    fast = calculator.calculate(
        AutonomyEvidence(
            correct=True,
            assistance_level=AssistanceLevel.NONE,
            hints_used=0,
            attempt_count=1,
            response_time_seconds=5,
        )
    )

    slow = calculator.calculate(
        AutonomyEvidence(
            correct=True,
            assistance_level=AssistanceLevel.NONE,
            hints_used=0,
            attempt_count=1,
            response_time_seconds=600,
        )
    )

    assert fast.score == slow.score == 100


def test_missing_evidence_is_not_assumed_autonomous():
    result = AutonomyCalculator().from_attempt_evidence(
        correct=True,
        evidence=None,
    )

    assert result.score == 0
    assert result.independently_correct is False
    assert result.requires_independent_verification is True


def test_attempt_evidence_adapter():
    result = AutonomyCalculator().from_attempt_evidence(
        correct=True,
        evidence=AttemptAnswerEvidence(
            assistance_level=AssistanceLevel.LIGHT_HINT,
            hints_used=1,
            attempt_count=2,
            response_time_seconds=37,
        ),
    )

    assert result.score == 65
    assert result.independently_correct is False
