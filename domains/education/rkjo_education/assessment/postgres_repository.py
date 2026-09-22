"""PostgreSQL assessment repository."""

from __future__ import annotations

from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from .models import (
    Assessment,
    Attempt,
    AttemptAnswerEvidence,
    AttemptStatus,
    Question,
)


class PostgresAssessmentRepository:
    def __init__(self, database_url: str) -> None:
        if not database_url.strip():
            raise ValueError("database_url must not be empty.")
        self.database_url = database_url
        self._ensure_schema()

    def _connect(self):
        return psycopg.connect(self.database_url)

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS education_assessments (
                    tenant_id UUID NOT NULL,
                    assessment_id UUID NOT NULL,
                    course_id UUID NOT NULL,
                    title TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (tenant_id, assessment_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS education_assessment_questions (
                    tenant_id UUID NOT NULL,
                    assessment_id UUID NOT NULL,
                    question_id UUID NOT NULL,
                    prompt TEXT NOT NULL,
                    correct_answer TEXT NOT NULL,
                    points INTEGER NOT NULL CHECK (points > 0),
                    competency_code TEXT,
                    PRIMARY KEY (tenant_id, assessment_id, question_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS education_assessment_attempts (
                    tenant_id UUID NOT NULL,
                    attempt_id UUID NOT NULL,
                    assessment_id UUID NOT NULL,
                    learner_id UUID NOT NULL,
                    answers JSONB NOT NULL DEFAULT '{}'::jsonb,
                    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
                    status TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    max_score INTEGER NOT NULL,
                    percentage INTEGER NOT NULL,
                    started_at TIMESTAMPTZ NOT NULL,
                    submitted_at TIMESTAMPTZ,
                    PRIMARY KEY (tenant_id, attempt_id),
                    CHECK (percentage BETWEEN 0 AND 100)
                )
                """
            )
            connection.execute(
                """
                ALTER TABLE education_assessment_attempts
                ADD COLUMN IF NOT EXISTS evidence JSONB NOT NULL DEFAULT '{}'::jsonb
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_education_assessment_questions_tenant_question
                ON education_assessment_questions (
                    tenant_id,
                    question_id
                )
                """
            )

    def save_assessment(self, assessment: Assessment) -> Assessment:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO education_assessments (
                    tenant_id, assessment_id, course_id, title, created_at
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, assessment_id)
                DO UPDATE SET title = EXCLUDED.title, course_id = EXCLUDED.course_id
                """,
                (
                    assessment.tenant_id,
                    assessment.id,
                    assessment.course_id,
                    assessment.title,
                    assessment.created_at,
                ),
            )
            connection.execute(
                """
                DELETE FROM education_assessment_questions
                WHERE tenant_id = %s AND assessment_id = %s
                """,
                (assessment.tenant_id, assessment.id),
            )
            for question in assessment.questions:
                connection.execute(
                    """
                    INSERT INTO education_assessment_questions (
                        tenant_id, assessment_id, question_id, prompt,
                        correct_answer, points, competency_code
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        assessment.tenant_id,
                        assessment.id,
                        question.id,
                        question.prompt,
                        question.correct_answer,
                        question.points,
                        question.competency_code,
                    ),
                )
        return assessment

    def get_assessment(self, *, tenant_id: UUID, assessment_id: UUID) -> Assessment | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT course_id, title, created_at
                FROM education_assessments
                WHERE tenant_id = %s AND assessment_id = %s
                """,
                (tenant_id, assessment_id),
            ).fetchone()
            if row is None:
                return None
            question_rows = connection.execute(
                """
                SELECT question_id, prompt, correct_answer, points, competency_code
                FROM education_assessment_questions
                WHERE tenant_id = %s AND assessment_id = %s
                ORDER BY question_id
                """,
                (tenant_id, assessment_id),
            ).fetchall()
        return Assessment(
            tenant_id=tenant_id,
            course_id=row[0],
            title=row[1],
            id=assessment_id,
            created_at=row[2],
            questions=[
                Question(
                    tenant_id=tenant_id,
                    id=q[0],
                    prompt=q[1],
                    correct_answer=q[2],
                    points=q[3],
                    competency_code=q[4],
                )
                for q in question_rows
            ],
        )

    def get_question(
        self,
        *,
        tenant_id: UUID,
        question_id: UUID,
    ) -> Question | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    prompt,
                    correct_answer,
                    points,
                    competency_code
                FROM education_assessment_questions
                WHERE tenant_id = %s
                  AND question_id = %s
                LIMIT 1
                """,
                (tenant_id, question_id),
            ).fetchone()

        if row is None:
            return None

        return Question(
            tenant_id=tenant_id,
            id=question_id,
            prompt=row[0],
            correct_answer=row[1],
            points=row[2],
            competency_code=row[3],
        )

    def save_attempt(self, attempt: Attempt) -> Attempt:
        answers = {str(key): value for key, value in attempt.answers.items()}
        evidence = {
            str(question_id): {
                "assistance_level": int(item.assistance_level),
                "hints_used": item.hints_used,
                "attempt_count": item.attempt_count,
                "response_time_seconds": item.response_time_seconds,
            }
            for question_id, item in attempt.evidence.items()
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO education_assessment_attempts (
                    tenant_id, attempt_id, assessment_id, learner_id,
                    answers, evidence, status, score, max_score, percentage,
                    started_at, submitted_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, attempt_id)
                DO UPDATE SET
                    answers = EXCLUDED.answers,
                    evidence = EXCLUDED.evidence,
                    status = EXCLUDED.status,
                    score = EXCLUDED.score,
                    max_score = EXCLUDED.max_score,
                    percentage = EXCLUDED.percentage,
                    submitted_at = EXCLUDED.submitted_at
                """,
                (
                    attempt.tenant_id,
                    attempt.id,
                    attempt.assessment_id,
                    attempt.learner_id,
                    Jsonb(answers),
                    Jsonb(evidence),
                    attempt.status.value,
                    attempt.score,
                    attempt.max_score,
                    attempt.percentage,
                    attempt.started_at,
                    attempt.submitted_at,
                ),
            )
        return attempt

    def get_attempt(self, *, tenant_id: UUID, attempt_id: UUID) -> Attempt | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT assessment_id, learner_id, answers, evidence, status, score,
                       max_score, percentage, started_at, submitted_at
                FROM education_assessment_attempts
                WHERE tenant_id = %s AND attempt_id = %s
                """,
                (tenant_id, attempt_id),
            ).fetchone()
        if row is None:
            return None
        answers = {UUID(key): value for key, value in dict(row[2]).items()}
        evidence = {
            UUID(key): AttemptAnswerEvidence(
                assistance_level=value["assistance_level"],
                hints_used=value.get("hints_used", 0),
                attempt_count=value.get("attempt_count", 1),
                response_time_seconds=value.get("response_time_seconds"),
            )
            for key, value in dict(row[3] or {}).items()
        }
        return Attempt(
            tenant_id=tenant_id,
            assessment_id=row[0],
            learner_id=row[1],
            id=attempt_id,
            answers=answers,
            evidence=evidence,
            status=AttemptStatus(row[4]),
            score=row[5],
            max_score=row[6],
            percentage=row[7],
            started_at=row[8],
            submitted_at=row[9],
        )
