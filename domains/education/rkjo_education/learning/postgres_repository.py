"""PostgreSQL learning repository."""

from __future__ import annotations

from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from .models import Competency, Enrollment, EnrollmentStatus, LearningProgress


class PostgresLearningRepository:
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
                CREATE TABLE IF NOT EXISTS education_enrollments (
                    tenant_id UUID NOT NULL,
                    enrollment_id UUID NOT NULL,
                    learner_id UUID NOT NULL,
                    curriculum_id UUID NOT NULL,
                    status TEXT NOT NULL,
                    enrolled_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (tenant_id, enrollment_id),
                    UNIQUE (tenant_id, learner_id, curriculum_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS education_competencies (
                    tenant_id UUID NOT NULL,
                    competency_id UUID NOT NULL,
                    code TEXT NOT NULL,
                    label TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, competency_id),
                    UNIQUE (tenant_id, code)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS education_learning_progress (
                    tenant_id UUID NOT NULL,
                    progress_id UUID NOT NULL,
                    learner_id UUID NOT NULL,
                    course_id UUID NOT NULL,
                    completion_percent INTEGER NOT NULL,
                    competency_scores JSONB NOT NULL DEFAULT '{}'::jsonb,
                    updated_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (tenant_id, progress_id),
                    UNIQUE (tenant_id, learner_id, course_id),
                    CHECK (completion_percent BETWEEN 0 AND 100)
                )
                """
            )

    def save_enrollment(self, enrollment: Enrollment) -> Enrollment:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO education_enrollments (
                    tenant_id, enrollment_id, learner_id, curriculum_id,
                    status, enrolled_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, enrollment_id)
                DO UPDATE SET status = EXCLUDED.status
                """,
                (
                    enrollment.tenant_id,
                    enrollment.id,
                    enrollment.learner_id,
                    enrollment.curriculum_id,
                    enrollment.status.value,
                    enrollment.enrolled_at,
                ),
            )
        return enrollment

    def find_enrollment(
        self, *, tenant_id: UUID, learner_id: UUID, curriculum_id: UUID
    ) -> Enrollment | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT enrollment_id, status, enrolled_at
                FROM education_enrollments
                WHERE tenant_id = %s AND learner_id = %s AND curriculum_id = %s
                """,
                (tenant_id, learner_id, curriculum_id),
            ).fetchone()
        if row is None:
            return None
        return Enrollment(
            tenant_id=tenant_id,
            learner_id=learner_id,
            curriculum_id=curriculum_id,
            id=row[0],
            status=EnrollmentStatus(row[1]),
            enrolled_at=row[2],
        )

    def save_competency(self, competency: Competency) -> Competency:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO education_competencies (
                    tenant_id, competency_id, code, label
                ) VALUES (%s, %s, %s, %s)
                ON CONFLICT (tenant_id, competency_id)
                DO UPDATE SET code = EXCLUDED.code, label = EXCLUDED.label
                """,
                (competency.tenant_id, competency.id, competency.code, competency.label),
            )
        return competency

    def list_competencies(self, *, tenant_id: UUID) -> list[Competency]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT competency_id, code, label
                FROM education_competencies
                WHERE tenant_id = %s
                ORDER BY code
                """,
                (tenant_id,),
            ).fetchall()
        return [
            Competency(tenant_id=tenant_id, id=row[0], code=row[1], label=row[2])
            for row in rows
        ]

    def save_progress(self, progress: LearningProgress) -> LearningProgress:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO education_learning_progress (
                    tenant_id, progress_id, learner_id, course_id,
                    completion_percent, competency_scores, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, learner_id, course_id)
                DO UPDATE SET
                    completion_percent = EXCLUDED.completion_percent,
                    competency_scores = EXCLUDED.competency_scores,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    progress.tenant_id,
                    progress.id,
                    progress.learner_id,
                    progress.course_id,
                    progress.completion_percent,
                    Jsonb(progress.competency_scores),
                    progress.updated_at,
                ),
            )
        return progress

    def find_progress(
        self, *, tenant_id: UUID, learner_id: UUID, course_id: UUID
    ) -> LearningProgress | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT progress_id, completion_percent, competency_scores, updated_at
                FROM education_learning_progress
                WHERE tenant_id = %s AND learner_id = %s AND course_id = %s
                """,
                (tenant_id, learner_id, course_id),
            ).fetchone()
        if row is None:
            return None
        return LearningProgress(
            tenant_id=tenant_id,
            learner_id=learner_id,
            course_id=course_id,
            id=row[0],
            completion_percent=row[1],
            competency_scores=dict(row[2]),
            updated_at=row[3],
        )
