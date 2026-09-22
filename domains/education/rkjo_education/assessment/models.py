from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from rkjo_education.policy import AssistanceLevel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AttemptStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"


@dataclass(slots=True)
class Question:
    tenant_id: UUID
    prompt: str
    correct_answer: str
    points: int = 1
    competency_code: str | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        self.prompt = self.prompt.strip()
        self.correct_answer = self.correct_answer.strip()
        if not self.prompt or not self.correct_answer:
            raise ValueError("prompt and correct_answer are required")
        if self.points <= 0:
            raise ValueError("points must be greater than zero")
        if self.competency_code is not None:
            self.competency_code = self.competency_code.strip() or None


@dataclass(slots=True)
class Assessment:
    tenant_id: UUID
    course_id: UUID
    title: str
    questions: list[Question] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)

    def add_question(self, question: Question) -> None:
        if question.tenant_id != self.tenant_id:
            raise ValueError("question tenant must match assessment tenant")
        self.questions.append(question)


@dataclass(slots=True)
class AttemptAnswerEvidence:
    assistance_level: AssistanceLevel = AssistanceLevel.NONE
    hints_used: int = 0
    attempt_count: int = 1
    response_time_seconds: int | None = None

    def __post_init__(self) -> None:
        self.assistance_level = AssistanceLevel(self.assistance_level)
        if self.hints_used < 0:
            raise ValueError("hints_used must be greater than or equal to zero")
        if self.attempt_count < 1:
            raise ValueError("attempt_count must be greater than or equal to one")
        if self.response_time_seconds is not None and self.response_time_seconds < 0:
            raise ValueError(
                "response_time_seconds must be greater than or equal to zero"
            )


@dataclass(slots=True)
class Attempt:
    tenant_id: UUID
    assessment_id: UUID
    learner_id: UUID
    id: UUID = field(default_factory=uuid4)
    answers: dict[UUID, str] = field(default_factory=dict)
    evidence: dict[UUID, AttemptAnswerEvidence] = field(default_factory=dict)
    status: AttemptStatus = AttemptStatus.IN_PROGRESS
    score: int = 0
    max_score: int = 0
    percentage: int = 0
    started_at: datetime = field(default_factory=utc_now)
    submitted_at: datetime | None = None

    def answer(
        self,
        question_id: UUID,
        value: str,
        *,
        evidence: AttemptAnswerEvidence | None = None,
    ) -> None:
        if self.status == AttemptStatus.SUBMITTED:
            raise ValueError("submitted attempt cannot be modified")
        self.answers[question_id] = value.strip()
        if evidence is not None:
            self.evidence[question_id] = evidence

    def submit(self, assessment: Assessment) -> None:
        if self.status == AttemptStatus.SUBMITTED:
            raise ValueError("attempt is already submitted")
        score = 0
        max_score = 0
        for question in assessment.questions:
            max_score += question.points
            answer = self.answers.get(question.id, "").strip().casefold()
            if answer == question.correct_answer.strip().casefold():
                score += question.points
        self.score = score
        self.max_score = max_score
        self.percentage = 0 if max_score == 0 else round((score / max_score) * 100)
        self.status = AttemptStatus.SUBMITTED
        self.submitted_at = utc_now()
