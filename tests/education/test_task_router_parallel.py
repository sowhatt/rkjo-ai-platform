import pytest

from rkjo_education.model_gateway.task_router import Discipline, Task, route_education_task


def test_math_uses_symbolic_verifier():
    plan = route_education_task(Discipline.MATHEMATICS, Task.SYMBOLIC_CALCULATION)
    assert plan.verifier == "sympy"
    assert plan.primary == "general_llm"


def test_medical_image_does_not_claim_unconfigured_provider():
    plan = route_education_task(Discipline.MEDICINE, Task.MEDICAL_IMAGE)
    assert plan.requires_human_review
    assert "unconfigured" in plan.primary


@pytest.mark.parametrize(
    ("discipline", "task"),
    [
        (Discipline.BIOLOGY, Task.MEDICAL_IMAGE),
        (Discipline.GENERAL, Task.SYMBOLIC_CALCULATION),
    ],
)
def test_invalid_specialist_pair_rejected(discipline, task):
    with pytest.raises(ValueError):
        route_education_task(discipline, task)
