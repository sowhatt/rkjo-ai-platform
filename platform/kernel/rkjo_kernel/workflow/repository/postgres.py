"""PostgreSQL implementation of WorkflowRepository."""

from __future__ import annotations

import json
from typing import Any

import psycopg

from rkjo_kernel.workflow.models.workflow_execution import WorkflowExecution
from rkjo_kernel.workflow.repository.serializer import (
    workflow_execution_from_dict,
    workflow_execution_to_dict,
)


class PostgreSQLWorkflowRepository:
    """Persist workflow executions in PostgreSQL JSONB."""

    def __init__(
        self,
        database_url: str,
    ) -> None:
        if not database_url or not database_url.strip():
            raise ValueError(
                "database_url must not be empty."
            )

        self.database_url = database_url

    def initialize_schema(self) -> None:
        """Create workflow persistence table when missing."""

        query = """
        CREATE TABLE IF NOT EXISTS workflow_executions (
            execution_id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            status TEXT NOT NULL,
            payload JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
                DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS
            idx_workflow_executions_workflow_id
        ON workflow_executions(workflow_id);

        CREATE INDEX IF NOT EXISTS
            idx_workflow_executions_status
        ON workflow_executions(status);
        """

        with psycopg.connect(
            self.database_url
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)

    def save(
        self,
        execution: WorkflowExecution,
    ) -> None:
        """Insert or update workflow execution state."""

        payload = workflow_execution_to_dict(
            execution
        )

        query = """
        INSERT INTO workflow_executions (
            execution_id,
            workflow_id,
            status,
            payload,
            created_at,
            updated_at
        )
        VALUES (
            %s,
            %s,
            %s,
            %s::jsonb,
            %s,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (execution_id)
        DO UPDATE SET
            workflow_id = EXCLUDED.workflow_id,
            status = EXCLUDED.status,
            payload = EXCLUDED.payload,
            updated_at = CURRENT_TIMESTAMP;
        """

        with psycopg.connect(
            self.database_url
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (
                        execution.execution_id,
                        execution.definition.workflow_id,
                        execution.status.value,
                        json.dumps(payload),
                        execution.created_at,
                    ),
                )

    def get(
        self,
        execution_id: str,
    ) -> WorkflowExecution | None:
        """Load one workflow execution."""

        query = """
        SELECT payload
        FROM workflow_executions
        WHERE execution_id = %s;
        """

        with psycopg.connect(
            self.database_url
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (execution_id,),
                )
                row = cursor.fetchone()

        if row is None:
            return None

        payload: dict[str, Any] = row[0]

        return workflow_execution_from_dict(
            payload
        )

    def delete(
        self,
        execution_id: str,
    ) -> None:
        """Delete an execution when present."""

        query = """
        DELETE FROM workflow_executions
        WHERE execution_id = %s;
        """

        with psycopg.connect(
            self.database_url
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (execution_id,),
                )

    def exists(
        self,
        execution_id: str,
    ) -> bool:
        """Return whether an execution exists."""

        query = """
        SELECT EXISTS (
            SELECT 1
            FROM workflow_executions
            WHERE execution_id = %s
        );
        """

        with psycopg.connect(
            self.database_url
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (execution_id,),
                )
                row = cursor.fetchone()

        return bool(row and row[0])

    def list_all(
        self,
    ) -> list[WorkflowExecution]:
        """Return all persisted executions."""

        query = """
        SELECT payload
        FROM workflow_executions
        ORDER BY created_at ASC;
        """

        with psycopg.connect(
            self.database_url
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()

        return [
            workflow_execution_from_dict(row[0])
            for row in rows
        ]
