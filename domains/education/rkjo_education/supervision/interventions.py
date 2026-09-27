from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

import psycopg
from pydantic import BaseModel, Field


class TeacherInterventionType(StrEnum):
    REQUEST_NEW_PROOF = "request_new_proof"
    ASSIGN_CONSOLIDATION = "assign_consolidation"
    SEND_MESSAGE = "send_message"


class TeacherInterventionStatus(StrEnum):
    REQUESTED = "requested"


class TeacherIntervention(BaseModel):
    intervention_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    learner_id: UUID
    intervention_type: TeacherInterventionType
    message: str | None = None
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: TeacherInterventionStatus = TeacherInterventionStatus.REQUESTED


class TeacherInterventionStore:
    """Tenant-scoped intervention command store for isolated unit tests."""

    def __init__(self) -> None:
        self._items: dict[tuple[UUID, UUID], list[TeacherIntervention]] = {}

    def create(self, intervention: TeacherIntervention) -> TeacherIntervention:
        key = (intervention.tenant_id, intervention.learner_id)
        self._items.setdefault(key, []).append(intervention)
        return intervention.model_copy(deep=True)

    def list_for_learner(self, *, tenant_id: UUID, learner_id: UUID) -> list[TeacherIntervention]:
        return [item.model_copy(deep=True) for item in self._items.get((tenant_id, learner_id), [])]


class PostgresTeacherInterventionStore:
    """Durable tenant-scoped teacher interventions."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def initialize_schema(self) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS education_teacher_interventions (
                    intervention_id UUID PRIMARY KEY,
                    tenant_id UUID NOT NULL,
                    learner_id UUID NOT NULL,
                    intervention_type TEXT NOT NULL,
                    message TEXT,
                    requested_at TIMESTAMPTZ NOT NULL,
                    status TEXT NOT NULL,
                    intervention_json JSONB NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_education_teacher_interventions_learner
                ON education_teacher_interventions
                (tenant_id, learner_id, requested_at, intervention_id)
                """
            )

    def create(self, intervention: TeacherIntervention) -> TeacherIntervention:
        payload = intervention.model_dump(mode="json")
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """
                INSERT INTO education_teacher_interventions (
                    intervention_id, tenant_id, learner_id, intervention_type,
                    message, requested_at, status, intervention_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (intervention_id) DO NOTHING
                """,
                (
                    intervention.intervention_id,
                    intervention.tenant_id,
                    intervention.learner_id,
                    intervention.intervention_type.value,
                    intervention.message,
                    intervention.requested_at,
                    intervention.status.value,
                    json.dumps(payload),
                ),
            )
        return intervention.model_copy(deep=True)

    def list_for_learner(self, *, tenant_id: UUID, learner_id: UUID) -> list[TeacherIntervention]:
        with psycopg.connect(self.database_url) as connection:
            rows = connection.execute(
                """
                SELECT intervention_json
                FROM education_teacher_interventions
                WHERE tenant_id = %s AND learner_id = %s
                ORDER BY requested_at ASC, intervention_id ASC
                """,
                (tenant_id, learner_id),
            ).fetchall()
        return [TeacherIntervention.model_validate(row[0]) for row in rows]
