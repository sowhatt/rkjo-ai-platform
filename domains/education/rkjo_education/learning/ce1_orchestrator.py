"""CE1 learning flow integrating tutor stages, assessment policy and model routing.

Pure domain service: no HTTP, no data persistence and no LLM call. This keeps the
pedagogical policy independently testable before JWT-protected API integration.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from rkjo_education.tutor.guided_lesson import (
    GuidedLesson, LessonPhase, advance_lesson, request_hint, submit_proof,
)
from rkjo_education.learning.next_action_policy import (
    LearningSignals, ActionDecision, recommend_next_action,
)
from rkjo_education.model_gateway.task_router import (
    Discipline, Task, RoutingPlan, route_education_task,
)


class TurnKind(str, Enum):
    START = "start"
    UNDERSTOOD = "understood"
    NEED_EXPLANATION = "need_explanation"
    HINT = "hint"
    ANSWER = "answer"


@dataclass(frozen=True)
class Ce1LearningSession:
    lesson: GuidedLesson
    guided_attempts: int = 0
    proof_attempts: int = 0
    guided_correct: bool = False
    proof_correct: bool | None = None
    additional_explanations: int = 0


@dataclass(frozen=True)
class Ce1TurnResult:
    session: Ce1LearningSession
    feedback: str
    next_action: ActionDecision
    routing_plan: RoutingPlan


def new_session(learner_id: str) -> Ce1LearningSession:
    if not learner_id.strip():
        raise ValueError("A learner identifier is required")
    return Ce1LearningSession(
        lesson=GuidedLesson(learner_id=learner_id, objective="CE1.MATH.ADD.PASSAGE_DIZAINE"),
    )


def _decision(session: Ce1LearningSession) -> ActionDecision:
    assessed = session.guided_attempts > 0 or session.proof_attempts > 0
    last_correct = session.proof_correct if session.proof_correct is not None else (
        session.guided_correct if session.guided_attempts > 0 else None
    )
    return recommend_next_action(LearningSignals(
        assessed=assessed,
        last_answer_correct=last_correct,
        hints_used=session.lesson.hints_used,
        autonomous_proof_passed=bool(session.proof_correct),
    ))


def transition(
    session: Ce1LearningSession,
    kind: TurnKind,
    answer: int | None = None,
) -> Ce1TurnResult:
    """Advance a domain session. An aided success never yields autonomous mastery."""
    lesson = session.lesson
    route = route_education_task(Discipline.MATHEMATICS, Task.SYMBOLIC_CALCULATION)
    feedback: str

    if kind == TurnKind.START:
        if lesson.phase != LessonPhase.EXPLAIN:
            raise ValueError("Session already started")
        # Require a comprehension signal rather than automatically claiming learning.
        session = replace(session, lesson=advance_lesson(lesson))
        feedback = "Observe comment compléter 8 pour atteindre 10. As-tu compris ?"
    elif kind == TurnKind.UNDERSTOOD:
        if lesson.phase != LessonPhase.CHECK:
            raise ValueError("Comprehension response expected")
        session = replace(session, lesson=advance_lesson(lesson, understood=True))
        feedback = "À toi de calculer 8 + 5."
    elif kind == TurnKind.NEED_EXPLANATION:
        if lesson.phase not in (LessonPhase.CHECK, LessonPhase.PRACTICE):
            raise ValueError("No assistance permitted in independent proof")
        if lesson.phase == LessonPhase.CHECK:
            lesson = advance_lesson(lesson, understood=False)
            lesson = advance_lesson(lesson)
        else:
            lesson = request_hint(lesson)
        session = replace(session, lesson=lesson, additional_explanations=session.additional_explanations + 1)
        feedback = "Pour former 10, prends 2 dans 5 : 8 + 2 = 10, puis ajoute les 3 restants."
    elif kind == TurnKind.HINT:
        if lesson.phase != LessonPhase.PRACTICE:
            raise ValueError("Hints forbidden outside guided practice")
        session = replace(session, lesson=request_hint(lesson))
        feedback = "Décompose 5 en 2 + 3 et complète d'abord la dizaine."
    elif kind == TurnKind.ANSWER:
        if type(answer) is not int or answer < 0:
            raise ValueError("An integer answer is required")
        if lesson.phase == LessonPhase.PRACTICE:
            correct = answer == 13
            session = replace(
                session,
                guided_attempts=session.guided_attempts + 1,
                guided_correct=correct,
                lesson=advance_lesson(lesson) if correct else lesson,
            )
            feedback = (
                "Entraînement réussi. Maintenant résous 7 + 6 sans indice."
                if correct else "Essaie encore : combien manque-t-il à 8 pour faire 10 ?"
            )
        elif lesson.phase == LessonPhase.PROOF:
            correct = answer == 13
            session = replace(
                session,
                proof_attempts=session.proof_attempts + 1,
                proof_correct=correct,
                lesson=submit_proof(lesson, correct=correct, assisted=False),
            )
            feedback = "Preuve autonome réussie." if correct else "Preuve non réussie. Revois la méthode."
        else:
            raise ValueError("Answers expected only in guided practice or independent proof")
    else:
        raise ValueError(f"Unsupported turn: {kind}")

    return Ce1TurnResult(
        session=session,
        feedback=feedback,
        next_action=_decision(session),
        routing_plan=route,
    )
