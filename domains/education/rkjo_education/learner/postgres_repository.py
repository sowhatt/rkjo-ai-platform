"""PostgreSQL learner repository."""

from __future__ import annotations

from uuid import UUID

import psycopg

from .models import LearnerProfile, LearnerStatus


class PostgresLearnerRepository:
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
                CREATE TABLE IF NOT EXISTS education_learners (
                    tenant_id UUID NOT NULL,
                    learner_id UUID NOT NULL,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    level TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (tenant_id, learner_id)
                )
                """
            )

    def save(self, learner: LearnerProfile) -> LearnerProfile:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO education_learners (
                    tenant_id, learner_id, first_name, last_name,
                    level, status, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, learner_id)
                DO UPDATE SET
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    level = EXCLUDED.level,
                    status = EXCLUDED.status,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    learner.tenant_id,
                    learner.id,
                    learner.first_name,
                    learner.last_name,
                    learner.level,
                    learner.status.value,
                    learner.created_at,
                    learner.updated_at,
                ),
            )
        return learner

    def get(self, *, tenant_id: UUID, learner_id: UUID) -> LearnerProfile | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT first_name, last_name, level, status, created_at, updated_at
                FROM education_learners
                WHERE tenant_id = %s AND learner_id = %s
                """,
                (tenant_id, learner_id),
            ).fetchone()
        if row is None:
            return None
        return LearnerProfile(
            tenant_id=tenant_id,
            id=learner_id,
            first_name=row[0],
            last_name=row[1],
            level=row[2],
            status=LearnerStatus(row[3]),
            created_at=row[4],
            updated_at=row[5],
        )

    def list(self, *, tenant_id: UUID) -> list[LearnerProfile]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT learner_id, first_name, last_name, level, status, created_at, updated_at
                FROM education_learners
                WHERE tenant_id = %s
                ORDER BY last_name, first_name, learner_id
                """,
                (tenant_id,),
            ).fetchall()
        return [
            LearnerProfile(
                tenant_id=tenant_id,
                id=row[0],
                first_name=row[1],
                last_name=row[2],
                level=row[3],
                status=LearnerStatus(row[4]),
                created_at=row[5],
                updated_at=row[6],
            )
            for row in rows
        ]
