"""Persistent PostgreSQL document hash registry."""

from __future__ import annotations

import psycopg
from psycopg import sql

from rkjo_kernel.rag.deduplication import (
    DocumentHashRegistry,
)


class PostgresDocumentHashRegistry(
    DocumentHashRegistry
):
    """Persist ingested document hashes in PostgreSQL."""

    def __init__(
        self,
        *,
        database_url: str,
        table_name: str = "rag_document_hashes",
    ) -> None:
        if not database_url.strip():
            raise ValueError(
                "database_url must not be empty."
            )

        if not table_name.strip():
            raise ValueError(
                "table_name must not be empty."
            )

        self.database_url = database_url
        self.table_name = table_name.strip()

    def initialize_schema(self) -> None:
        """Create persistent deduplication table."""

        with psycopg.connect(
            self.database_url,
            autocommit=True,
        ) as connection:
            connection.execute(
                sql.SQL(
                    """
                    CREATE TABLE IF NOT EXISTS {} (
                        content_hash TEXT PRIMARY KEY,
                        document_id TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL
                            DEFAULT NOW()
                    )
                    """
                ).format(
                    sql.Identifier(
                        self.table_name
                    )
                )
            )

            document_index = sql.Identifier(
                f"{self.table_name}_document_idx"
            )

            connection.execute(
                sql.SQL(
                    """
                    CREATE INDEX IF NOT EXISTS {}
                    ON {} (document_id)
                    """
                ).format(
                    document_index,
                    sql.Identifier(
                        self.table_name
                    ),
                )
            )

    def contains(
        self,
        content_hash: str,
    ) -> bool:
        """Return whether a content hash is already registered."""

        self._validate_hash(
            content_hash
        )

        with psycopg.connect(
            self.database_url
        ) as connection:
            row = connection.execute(
                sql.SQL(
                    """
                    SELECT 1
                    FROM {}
                    WHERE content_hash = %s
                    LIMIT 1
                    """
                ).format(
                    sql.Identifier(
                        self.table_name
                    )
                ),
                (
                    content_hash,
                ),
            ).fetchone()

        return row is not None

    def register(
        self,
        *,
        content_hash: str,
        document_id: str,
    ) -> None:
        """Register one document hash idempotently."""

        self._validate_hash(
            content_hash
        )

        if not document_id.strip():
            raise ValueError(
                "document_id must not be empty."
            )

        with psycopg.connect(
            self.database_url,
            autocommit=True,
        ) as connection:
            connection.execute(
                sql.SQL(
                    """
                    INSERT INTO {} (
                        content_hash,
                        document_id
                    )
                    VALUES (%s, %s)
                    ON CONFLICT (content_hash)
                    DO NOTHING
                    """
                ).format(
                    sql.Identifier(
                        self.table_name
                    )
                ),
                (
                    content_hash,
                    document_id,
                ),
            )

    def get_document_id(
        self,
        content_hash: str,
    ) -> str | None:
        """Return document id associated with a hash."""

        self._validate_hash(
            content_hash
        )

        with psycopg.connect(
            self.database_url
        ) as connection:
            row = connection.execute(
                sql.SQL(
                    """
                    SELECT document_id
                    FROM {}
                    WHERE content_hash = %s
                    """
                ).format(
                    sql.Identifier(
                        self.table_name
                    )
                ),
                (
                    content_hash,
                ),
            ).fetchone()

        if row is None:
            return None

        return str(
            row[0]
        )

    def count(self) -> int:
        """Return number of registered unique documents."""

        with psycopg.connect(
            self.database_url
        ) as connection:
            row = connection.execute(
                sql.SQL(
                    """
                    SELECT COUNT(*)
                    FROM {}
                    """
                ).format(
                    sql.Identifier(
                        self.table_name
                    )
                )
            ).fetchone()

        return int(
            row[0]
            if row is not None
            else 0
        )

    def drop_schema(self) -> None:
        """Drop registry table, intended for isolated tests."""

        with psycopg.connect(
            self.database_url,
            autocommit=True,
        ) as connection:
            connection.execute(
                sql.SQL(
                    """
                    DROP TABLE IF EXISTS {}
                    """
                ).format(
                    sql.Identifier(
                        self.table_name
                    )
                )
            )

    @staticmethod
    def _validate_hash(
        content_hash: str,
    ) -> None:
        if not content_hash.strip():
            raise ValueError(
                "content_hash must not be empty."
            )
