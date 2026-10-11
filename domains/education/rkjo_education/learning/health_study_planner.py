"""Deterministic starter plan; AI may propose priorities, not invent mastery."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta
from rkjo_education.learning.next_action_policy import LearningSignals, recommend_next_action


@dataclass(frozen=True, slots=True)
class StudySession:
    day: date
    ue_id: str
    activity: str
    minutes: int


def starter_study_plan(*, ue_id: str, start: date, exam: date, minutes_per_day: int,
                       signals: LearningSignals) -> tuple[StudySession, ...]:
    if not ue_id.strip() or minutes_per_day < 10 or minutes_per_day > 240:
        raise ValueError("Valid UE and 10-240 available minutes per day required")
    if exam <= start:
        raise ValueError("Exam must be later than start date")
    action = recommend_next_action(signals).action.value
    days = min((exam - start).days, 14)
    return tuple(
        StudySession(start + timedelta(days=i), ue_id, action if i == 0 else
                     ("review" if i % 3 == 2 else "practice"), minutes_per_day)
        for i in range(days)
    )
