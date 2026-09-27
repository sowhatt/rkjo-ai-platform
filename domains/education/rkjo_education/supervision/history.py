from __future__ import annotations

import json
from uuid import UUID

import psycopg

from rkjo_education.events import EducationLearningEvent


class PostgresLearningEventHistory:
    """Durable, append-only pedagogical event history used by supervision replay."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def initialize_schema(self) -> None:
        with psycopg.connect(self._database_url) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS education_learning_events (
                    event_id UUID PRIMARY KEY,
                    tenant_id UUID NOT NULL,
                    learner_id UUID NOT NULL,
                    occurred_at TIMESTAMPTZ NOT NULL,
                    event_type TEXT NOT NULL,
                    event_json JSONB NOT NULL
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_education_learning_events_tenant_learner_time
                ON education_learning_events (tenant_id, learner_id, occurred_at, event_id)
            """)

    def append(self, event: EducationLearningEvent) -> None:
        with psycopg.connect(self._database_url) as connection:
            connection.execute(
                """INSERT INTO education_learning_events
                   (event_id, tenant_id, learner_id, occurred_at, event_type, event_json)
                   VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                   ON CONFLICT (event_id) DO NOTHING""",
                (event.event_id, event.tenant_id, event.learner_id, event.occurred_at,
                 event.event_type.value, event.model_dump_json()),
            )

    def list_for_learner(self, *, tenant_id: UUID, learner_id: UUID) -> list[EducationLearningEvent]:
        with psycopg.connect(self._database_url) as connection:
            rows = connection.execute(
                """SELECT event_json FROM education_learning_events
                   WHERE tenant_id = %s AND learner_id = %s
                   ORDER BY occurred_at ASC, event_id ASC""",
                (tenant_id, learner_id),
            ).fetchall()
        return [EducationLearningEvent.model_validate(row[0]) for row in rows]
