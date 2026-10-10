"""Deterministic learning-session flow, independent of model providers.

A guided answer is practice, not proof of autonomous mastery.
"""
from dataclasses import dataclass, replace
from enum import Enum


class LessonPhase(str, Enum):
    EXPLAIN = "explain"
    CHECK = "check"
    PRACTICE = "practice"
    PROOF = "proof"
    REVIEW = "review"


@dataclass(frozen=True)
class GuidedLesson:
    learner_id: str
    objective: str
    phase: LessonPhase = LessonPhase.EXPLAIN
    hints_used: int = 0
    autonomous_proof_passed: bool = False


def advance_lesson(lesson: GuidedLesson, *, understood: bool | None = None) -> GuidedLesson:
    """Advance only when the required student signal is available."""
    if not lesson.learner_id.strip() or not lesson.objective.strip():
        raise ValueError("Learner and objective are required")
    if lesson.phase == LessonPhase.EXPLAIN:
        return replace(lesson, phase=LessonPhase.CHECK)
    if lesson.phase == LessonPhase.CHECK:
        if understood is None:
            raise ValueError("A comprehension answer is required")
        return replace(lesson, phase=LessonPhase.PRACTICE if understood else LessonPhase.EXPLAIN)
    if lesson.phase == LessonPhase.PRACTICE:
        return replace(lesson, phase=LessonPhase.PROOF)
    if lesson.phase == LessonPhase.PROOF:
        raise ValueError("Submit an autonomous proof result before reviewing")
    return lesson


def request_hint(lesson: GuidedLesson) -> GuidedLesson:
    if lesson.phase != LessonPhase.PRACTICE:
        raise ValueError("Hints are only available during guided practice")
    return replace(lesson, hints_used=min(3, lesson.hints_used + 1))


def submit_proof(lesson: GuidedLesson, *, correct: bool, assisted: bool = False) -> GuidedLesson:
    if lesson.phase != LessonPhase.PROOF:
        raise ValueError("Proof is only accepted in the proof phase")
    if assisted or lesson.hints_used < 0:
        raise ValueError("Proof must be completed without assistance")
    return replace(lesson, phase=LessonPhase.REVIEW, autonomous_proof_passed=correct)
