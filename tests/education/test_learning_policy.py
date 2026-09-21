import pytest

from rkjo_education.policy import (
    AssistanceLevel,
    LearningMode,
    LearningPolicyService,
)


@pytest.fixture
def policy():
    return LearningPolicyService()


def test_exam_forbids_all_assistance(policy):
    decision = policy.decide(
        mode=LearningMode.EXAM,
        requested_assistance=AssistanceLevel.EXPLAINED_SOLUTION,
    )

    assert decision.assistance_level is AssistanceLevel.NONE
    assert decision.allow_direct_answer is False
    assert decision.require_verification is False


def test_socratic_never_gives_direct_answer(policy):
    decision = policy.decide(
        mode=LearningMode.SOCRATIC,
        requested_assistance=AssistanceLevel.EXPLAINED_SOLUTION,
    )

    assert decision.assistance_level is AssistanceLevel.SOCRATIC_QUESTION
    assert decision.allow_direct_answer is False
    assert decision.require_verification is True


def test_guided_caps_assistance_at_guided_method(policy):
    decision = policy.decide(
        mode=LearningMode.GUIDED,
        requested_assistance=AssistanceLevel.EXPLAINED_SOLUTION,
    )

    assert decision.assistance_level is AssistanceLevel.GUIDED_METHOD
    assert decision.allow_direct_answer is False


def test_practice_can_allow_explained_solution(policy):
    decision = policy.decide(
        mode=LearningMode.PRACTICE,
        requested_assistance=AssistanceLevel.EXPLAINED_SOLUTION,
    )

    assert decision.assistance_level is AssistanceLevel.EXPLAINED_SOLUTION
    assert decision.allow_direct_answer is True
    assert decision.require_verification is True


def test_default_assistance_is_light_hint(policy):
    decision = policy.decide(
        mode=LearningMode.PRACTICE,
    )

    assert decision.assistance_level is AssistanceLevel.LIGHT_HINT
