"""Explainable next-learning-action policy; no synthetic mastery scores."""
from dataclasses import dataclass
from enum import Enum


class NextAction(str, Enum):
    DIAGNOSE = "diagnose"
    REMEDIATE = "remediate"
    PRACTICE = "practice"
    AUTONOMOUS_PROOF = "autonomous_proof"
    ADVANCE = "advance"


@dataclass(frozen=True)
class LearningSignals:
    assessed: bool
    last_answer_correct: bool | None = None
    hints_used: int = 0
    autonomous_proof_passed: bool = False
    missing_prerequisites: bool = False


@dataclass(frozen=True)
class ActionDecision:
    action: NextAction
    reason: str


def recommend_next_action(signals: LearningSignals) -> ActionDecision:
    """Conservative ordering: prerequisites, diagnostic, errors, proof, advance."""
    if signals.hints_used < 0:
        raise ValueError("hints_used must not be negative")
    if signals.missing_prerequisites:
        return ActionDecision(NextAction.REMEDIATE, "Missing prerequisites")
    if not signals.assessed or signals.last_answer_correct is None:
        return ActionDecision(NextAction.DIAGNOSE, "No observed assessment result")
    if not signals.last_answer_correct:
        return ActionDecision(NextAction.PRACTICE, "An observed answer was incorrect")
    if signals.autonomous_proof_passed and signals.hints_used == 0:
        return ActionDecision(NextAction.ADVANCE, "Autonomous proof passed without help")
    return ActionDecision(NextAction.AUTONOMOUS_PROOF, "Guided success still requires independent proof")
