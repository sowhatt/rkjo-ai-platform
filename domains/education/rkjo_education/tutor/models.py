from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TutorSource:
    citation: int
    document_id: str
    chunk_id: str
    score: float


@dataclass(frozen=True, slots=True)
class TutorAnswer:
    learner_id: UUID
    course_id: UUID
    answer: str
    adapted_question: str
    level: str
    completion_percent: int
    weak_competencies: list[str] = field(default_factory=list)
    sources: list[TutorSource] = field(default_factory=list)
