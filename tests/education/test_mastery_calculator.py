from rkjo_education.intelligence import (
    AutonomyResult,
    LearnerModelCalculator,
    LearnerObservation,
    MasteryCalculator,
    MasteryLevel,
    MasteryObservation,
)


def autonomy(
    score: int,
    *,
    independent: bool = False,
    verification: bool = False,
) -> AutonomyResult:
    return AutonomyResult(
        score=score,
        independently_correct=independent,
        requires_independent_verification=verification,
    )


def test_no_observation_means_not_demonstrated():
    result = MasteryCalculator().calculate([])

    assert result.level == MasteryLevel.NOT_DEMONSTRATED
    assert result.correct_observations == 0
    assert result.independent_successes == 0
    assert result.requires_proof_of_learning is False


def test_wrong_answer_does_not_demonstrate_mastery():
    result = MasteryCalculator().calculate(
        [
            MasteryObservation(
                correct=False,
                autonomy=autonomy(0),
            )
        ]
    )

    assert result.level == MasteryLevel.NOT_DEMONSTRATED
    assert result.independent_successes == 0


def test_assisted_success_is_developing():
    result = MasteryCalculator().calculate(
        [
            MasteryObservation(
                correct=True,
                autonomy=autonomy(
                    30,
                    verification=True,
                ),
            )
        ]
    )

    assert result.level == MasteryLevel.DEVELOPING
    assert result.requires_proof_of_learning is True


def test_explained_solution_cannot_create_mastery():
    result = MasteryCalculator().calculate(
        [
            MasteryObservation(
                correct=True,
                autonomy=autonomy(
                    0,
                    verification=True,
                ),
            ),
            MasteryObservation(
                correct=True,
                autonomy=autonomy(
                    0,
                    verification=True,
                ),
            ),
        ]
    )

    assert result.level == MasteryLevel.DEVELOPING
    assert result.independent_successes == 0
    assert result.requires_proof_of_learning is True


def test_one_independent_success_is_provisional():
    result = MasteryCalculator().calculate(
        [
            MasteryObservation(
                correct=True,
                autonomy=autonomy(
                    100,
                    independent=True,
                ),
            )
        ]
    )

    assert result.level == MasteryLevel.PROVISIONAL
    assert result.independent_successes == 1
    assert result.requires_proof_of_learning is True


def test_two_independent_successes_establish_mastery():
    result = MasteryCalculator().calculate(
        [
            MasteryObservation(
                correct=True,
                autonomy=autonomy(
                    100,
                    independent=True,
                ),
            ),
            MasteryObservation(
                correct=True,
                autonomy=autonomy(
                    100,
                    independent=True,
                ),
            ),
        ]
    )

    assert result.level == MasteryLevel.MASTERED
    assert result.independent_successes == 2
    assert result.requires_proof_of_learning is False


def test_assisted_success_followed_by_one_independent_is_provisional():
    result = MasteryCalculator().calculate(
        [
            MasteryObservation(
                correct=True,
                autonomy=autonomy(
                    30,
                    verification=True,
                ),
            ),
            MasteryObservation(
                correct=True,
                autonomy=autonomy(
                    100,
                    independent=True,
                ),
            ),
        ]
    )

    assert result.level == MasteryLevel.PROVISIONAL
    assert result.independent_successes == 1
    assert result.requires_proof_of_learning is True


def test_multiple_wrong_answers_do_not_create_mastery():
    result = MasteryCalculator().calculate(
        [
            MasteryObservation(
                correct=False,
                autonomy=autonomy(0),
            ),
            MasteryObservation(
                correct=False,
                autonomy=autonomy(0),
            ),
            MasteryObservation(
                correct=False,
                autonomy=autonomy(0),
            ),
        ]
    )

    assert result.level == MasteryLevel.NOT_DEMONSTRATED
    assert result.correct_observations == 0



def test_v23_mastery_is_capped_without_successful_proof():
    calculator = LearnerModelCalculator()
    observations = [LearnerObservation(score=1.0, weight=1.0) for _ in range(10)]
    assert calculator.mastery(observations, successful_proof=False) == 0.75
    assert calculator.mastery(observations, successful_proof=True) > 0.75


def test_v23_autonomy_uses_only_last_five_help_levels():
    calculator = LearnerModelCalculator()
    assert calculator.autonomy([1.0, 0.0, 0.25, 0.5, 0.75, 1.0]) == 0.5


def test_v23_retention_and_review_threshold():
    calculator = LearnerModelCalculator()
    state = calculator.calculate(
        observations=[LearnerObservation(score=.8, weight=1.0)],
        help_levels=[0.0],
        days_since_success=2.0,
        stability_days=2.0,
        successful_proof=True,
    )
    assert state.retention < 0.60
    assert state.review_due is True


def test_v23_stability_grows_on_spaced_success_and_shrinks_on_failure():
    calculator = LearnerModelCalculator()
    assert calculator.next_stability(
        current_stability_days=2,
        successful_no_help=True,
        spaced_at_least_one_day=True,
    ) == 5
    assert calculator.next_stability(
        current_stability_days=5,
        successful_no_help=False,
        failed=True,
    ) == 2.5


def test_v23_status_requires_proof_for_acquired():
    calculator = LearnerModelCalculator()
    observations = [LearnerObservation(score=1.0, weight=1.0) for _ in range(10)]
    fragile = calculator.calculate(
        observations=observations,
        help_levels=[0.0],
        days_since_success=0,
        successful_proof=False,
    )
    acquired = calculator.calculate(
        observations=observations,
        help_levels=[0.0],
        days_since_success=0,
        successful_proof=True,
    )
    assert fragile.status == "fragile"
    assert acquired.status == "acquired"
