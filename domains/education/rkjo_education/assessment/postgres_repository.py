"""PostgreSQL assessment repository."""

from __future__ import annotations

from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from .models import Assessment, Attempt, AttemptStatus, Question


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

    def save_attempt(self, attempt: Attempt) -> Attempt:
        answers = {str(key): value for key, value in attempt.answers.items()}
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO education_assessment_attempts (
                    tenant_id, attempt_id, assessment_id, learner_id,
                    answers, status, score, max_score, percentage,
                    started_at, submitted_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, attempt_id)
                DO UPDATE SET
                    answers = EXCLUDED.answers,
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
                SELECT assessment_id, learner_id, answers, status, score,
                       max_score, percentage, started_at, submitted_at
                FROM education_assessment_attempts
                WHERE tenant_id = %s AND attempt_id = %s
                """,
                (tenant_id, attempt_id),
            ).fetchone()
        if row is None:
            return None
        answers = {UUID(key): value for key, value in dict(row[2]).items()}
        return Attempt(
            tenant_id=tenant_id,
            assessment_id=row[0],
            learner_id=row[1],
            id=attempt_id,
            answers=answers,
            status=AttemptStatus(row[3]),
            score=row[4],
            max_score=row[5],
            percentage=row[6],
            started_at=row[7],
            submitted_at=row[8],
        )
