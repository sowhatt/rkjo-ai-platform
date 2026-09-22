from rkjo_education.intelligence import (
    AutonomyResult,
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
