"""PostgreSQL transactional workflow unit of work."""

from __future__ import annotations

import json
from typing import Any

import psycopg
from psycopg import Connection

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.workflow.models.workflow_execution import (
    WorkflowExecution,
)
from rkjo_kernel.workflow.outbox import OutboxMessage
from rkjo_kernel.workflow.repository.serializer import (
    workflow_execution_from_dict,
    workflow_execution_to_dict,
)


class PostgreSQLTransactionalWorkflowRepository:
    """Workflow repository bound to an existing transaction."""

    def __init__(
        self,
        connection: Connection,
    ) -> None:
        self._connection = connection

    def save(
        self,
        execution: WorkflowExecution,
    ) -> None:
        payload = workflow_execution_to_dict(execution)

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

        with self._connection.cursor() as cursor:
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
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT payload
                FROM workflow_executions
                WHERE execution_id = %s;
                """,
                (execution_id,),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        payload: dict[str, Any] = row[0]
        return workflow_execution_from_dict(payload)

    def delete(
        self,
        execution_id: str,
    ) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM workflow_executions
                WHERE execution_id = %s;
                """,
                (execution_id,),
            )

    def exists(
        self,
        execution_id: str,
    ) -> bool:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM workflow_executions
                    WHERE execution_id = %s
                );
                """,
                (execution_id,),
            )
            row = cursor.fetchone()

        return bool(row and row[0])

    def list_all(
        self,
    ) -> list[WorkflowExecution]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT payload
                FROM workflow_executions
                ORDER BY created_at ASC;
                """
            )
            rows = cursor.fetchall()

        return [
            workflow_execution_from_dict(row[0])
            for row in rows
        ]


class PostgreSQLTransactionalInboxStore:
    """Inbox store bound to an existing transaction."""

    def __init__(
        self,
        connection: Connection,
    ) -> None:
        self._connection = connection

    def contains(
        self,
        message_id: str,
    ) -> bool:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM workflow_inbox
                    WHERE message_id = %s
                );
                """,
                (message_id,),
            )
            row = cursor.fetchone()

        return bool(row and row[0])

    def mark_processed(
        self,
        message_id: str,
    ) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO workflow_inbox (
                    message_id
                )
                VALUES (%s)
                ON CONFLICT (message_id)
                DO NOTHING;
                """,
                (message_id,),
            )


class PostgreSQLTransactionalOutboxStore:
    """Outbox store bound to an existing transaction."""

    def __init__(
        self,
        connection: Connection,
    ) -> None:
        self._connection = connection

    def add(
        self,
        message: OutboxMessage,
    ) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO workflow_outbox (
                    outbox_id,
                    queue_name,
                    message_payload,
                    created_at
                )
                VALUES (
                    %s,
                    %s,
                    %s::jsonb,
                    %s
                )
                ON CONFLICT (outbox_id)
                DO NOTHING;
                """,
                (
                    message.outbox_id,
                    message.queue_name,
                    message.message.model_dump_json(),
                    message.created_at,
                ),
            )

    def pending(
        self,
        *,
        limit: int = 100,
    ) -> list[OutboxMessage]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    outbox_id,
                    queue_name,
                    message_payload,
                    created_at
                FROM workflow_outbox
                WHERE published_at IS NULL
                ORDER BY created_at ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED;
                """,
                (limit,),
            )
            rows = cursor.fetchall()

        return [
            OutboxMessage(
                outbox_id=row[0],
                queue_name=row[1],
                message=AgentMessage.model_validate(
                    row[2]
                ),
                created_at=row[3],
            )
            for row in rows
        ]

    def mark_published(
        self,
        outbox_id: str,
    ) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE workflow_outbox
                SET published_at = CURRENT_TIMESTAMP
                WHERE outbox_id = %s;
                """,
                (outbox_id,),
            )
            updated = cursor.rowcount

        if updated == 0:
            raise KeyError(
                f"Unknown outbox message '{outbox_id}'."
            )


class PostgreSQLWorkflowUnitOfWork:
    """One PostgreSQL transaction for workflow, inbox and outbox."""

    def __init__(
        self,
        database_url: str,
    ) -> None:
        if not database_url or not database_url.strip():
            raise ValueError(
                "database_url must not be empty."
            )

        self.database_url = database_url
        self._connection: Connection | None = None

        self.workflows = None
        self.inbox = None
        self.outbox = None

    def initialize_schema(self) -> None:
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

        CREATE TABLE IF NOT EXISTS workflow_inbox (
            message_id TEXT PRIMARY KEY,
            processed_at TIMESTAMPTZ NOT NULL
                DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS workflow_outbox (
            outbox_id TEXT PRIMARY KEY,
            queue_name TEXT NOT NULL,
            message_payload JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            published_at TIMESTAMPTZ NULL
        );

        CREATE INDEX IF NOT EXISTS
            idx_workflow_outbox_pending
        ON workflow_outbox(created_at)
        WHERE published_at IS NULL;
        """

        with psycopg.connect(
            self.database_url
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)

    def __enter__(
        self,
    ) -> "PostgreSQLWorkflowUnitOfWork":
        self._connection = psycopg.connect(
            self.database_url
        )

        self.workflows = (
            PostgreSQLTransactionalWorkflowRepository(
                self._connection
            )
        )
        self.inbox = PostgreSQLTransactionalInboxStore(
            self._connection
        )
        self.outbox = PostgreSQLTransactionalOutboxStore(
            self._connection
        )

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        if self._connection is None:
            return

        try:
            if exc_type is not None:
                self._connection.rollback()
            else:
                self._connection.rollback()
        finally:
            self._connection.close()
            self._connection = None

    def commit(self) -> None:
        if self._connection is None:
            raise RuntimeError(
                "Unit of work is not active."
            )

        self._connection.commit()

    def rollback(self) -> None:
        if self._connection is None:
            raise RuntimeError(
                "Unit of work is not active."
            )

        self._connection.rollback()
