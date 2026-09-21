from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum


class LearningMode(StrEnum):
    SOCRATIC = "socratic"
    GUIDED = "guided"
    PRACTICE = "practice"
    EXAM = "exam"


class AssistanceLevel(IntEnum):
    NONE = 0
    SOCRATIC_QUESTION = 1
    LIGHT_HINT = 2
    STRONG_HINT = 3
    GUIDED_METHOD = 4
    EXPLAINED_SOLUTION = 5


@dataclass(frozen=True, slots=True)
class LearningPolicyDecision:
    mode: LearningMode
    assistance_level: AssistanceLevel
    allow_direct_answer: bool
    require_verification: bool
    instruction: str
