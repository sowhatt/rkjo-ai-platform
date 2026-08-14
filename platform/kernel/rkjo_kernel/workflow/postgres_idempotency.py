"""PostgreSQL-backed idempotency store."""

from __future__ import annotations

import psycopg


class PostgreSQLProcessedMessageStore:
    """Persist processed message identifiers in PostgreSQL."""

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
        """Create processed-message table when missing."""

        query = """
        CREATE TABLE IF NOT EXISTS processed_messages (
            message_id TEXT PRIMARY KEY,
            processed_at TIMESTAMPTZ NOT NULL
                DEFAULT CURRENT_TIMESTAMP
        );
        """

        with psycopg.connect(
            self.database_url
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)

    def contains(
        self,
        message_id: str,
    ) -> bool:
        """Return whether the message was already processed."""

        query = """
        SELECT EXISTS (
            SELECT 1
            FROM processed_messages
            WHERE message_id = %s
        );
        """

        with psycopg.connect(
            self.database_url
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (message_id,),
                )
                row = cursor.fetchone()

        return bool(row and row[0])

    def mark_processed(
        self,
        message_id: str,
    ) -> None:
        """Mark a message as processed idempotently."""

        query = """
        INSERT INTO processed_messages (
            message_id
        )
        VALUES (%s)
        ON CONFLICT (message_id)
        DO NOTHING;
        """

        with psycopg.connect(
            self.database_url
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (message_id,),
                )
