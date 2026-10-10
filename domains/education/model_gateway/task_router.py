"""Auditable routing plans for educational AI tasks.

This module returns a plan, it does not download or call any external model.
Specialised medical models are candidates requiring separate evaluation.
"""
from dataclasses import dataclass
from enum import Enum


class Discipline(str, Enum):
    MATHEMATICS = "mathematics"
    MEDICINE = "medicine"
    BIOLOGY = "biology"
    GENERAL = "general"


class Task(str, Enum):
    EXPLAIN = "explain"
    SYMBOLIC_CALCULATION = "symbolic_calculation"
    MEDICAL_IMAGE = "medical_image"
    QUIZ = "quiz"


@dataclass(frozen=True)
class RoutingPlan:
    primary: str
    verifier: str | None
    reason: str
    requires_human_review: bool = False


def route_education_task(discipline: Discipline, task: Task) -> RoutingPlan:
    """Do not claim specialist models are deployed without provider configuration."""
    if task == Task.SYMBOLIC_CALCULATION:
        if discipline != Discipline.MATHEMATICS:
            raise ValueError("Symbolic calculator route requires mathematics")
        return RoutingPlan(
            primary="general_llm",
            verifier="sympy",
            reason="Verify symbolic results independently of the explanation",
        )
    if task == Task.MEDICAL_IMAGE:
        if discipline != Discipline.MEDICINE:
            raise ValueError("Medical image route requires medicine")
        return RoutingPlan(
            primary="unconfigured_medical_vision_candidate",
            verifier=None,
            reason="Medical image adapter must be benchmarked and configured before use",
            requires_human_review=True,
        )
    return RoutingPlan(
        primary="general_llm",
        verifier=None,
        reason="Pedagogical explanation or quiz; grounding and assessment belong to Learning Engine",
    )
