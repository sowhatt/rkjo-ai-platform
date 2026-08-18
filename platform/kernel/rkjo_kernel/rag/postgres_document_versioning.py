"""Persistent PostgreSQL RAG document version registry."""

from __future__ import annotations

from datetime import datetime

import psycopg
from psycopg import sql

from rkjo_kernel.rag.document_versioning import (
    DocumentVersion,
    DocumentVersionState,
)


class PostgresDocumentVersionRepository:
    """Persistent tenant-aware document version registry."""

    def __init__(
        self,
        *,
        database_url: str,
        document_table_name: str = "rag_documents",
        version_table_name: str = "rag_document_versions",
    ) -> None:
        if not database_url.strip():
            raise ValueError(
                "database_url must not be empty."
            )

        self.database_url = database_url
        self.document_table_name = (
            document_table_name.strip()
        )
        self.version_table_name = (
            version_table_name.strip()
        )

        if not self.document_table_name:
            raise ValueError(
                "document_table_name must not be empty."
            )

        if not self.version_table_name:
            raise ValueError(
                "version_table_name must not be empty."
            )

    def initialize_schema(self) -> None:
        with psycopg.connect(
            self.database_url,
            autocommit=True,
        ) as connection:
            documents = sql.Identifier(
                self.document_table_name
            )
            versions = sql.Identifier(
                self.version_table_name
            )

            connection.execute(
                sql.SQL(
                    """
                    CREATE TABLE IF NOT EXISTS {} (
                        document_id TEXT NOT NULL,
                        tenant_id TEXT NOT NULL,
                        current_version INTEGER NOT NULL
                            CHECK (current_version >= 1),
                        created_at TIMESTAMPTZ NOT NULL
                            DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL
                            DEFAULT NOW(),
                        PRIMARY KEY (
                            tenant_id,
                            document_id
                        )
                    )
                    """
                ).format(documents)
            )

            connection.execute(
                sql.SQL(
                    """
                    CREATE TABLE IF NOT EXISTS {} (
                        version_id UUID PRIMARY KEY,
                        document_id TEXT NOT NULL,
                        tenant_id TEXT NOT NULL,
                        version_number INTEGER NOT NULL
                            CHECK (version_number >= 1),
                        content_hash TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL
                            DEFAULT NOW(),
                        UNIQUE (
                            tenant_id,
                            document_id,
                            version_number
                        )
                    )
                    """
                ).format(versions)
            )

            connection.execute(
                sql.SQL(
                    """
                    CREATE INDEX IF NOT EXISTS {}
                    ON {} (
                        tenant_id,
                        document_id,
                        version_number DESC
                    )
                    """
                ).format(
                    sql.Identifier(
                        f"{self.version_table_name}_document_idx"
                    ),
                    versions,
                )
            )

    def get_document_state(
        self,
        *,
        document_id: str,
        tenant_id: str,
    ) -> DocumentVersionState | None:
        with psycopg.connect(
            self.database_url
        ) as connection:
            row = connection.execute(
                sql.SQL(
                    """
                    SELECT
                        document_id,
                        tenant_id,
                        current_version,
                        created_at,
                        updated_at
                    FROM {}
                    WHERE document_id = %s
                      AND tenant_id = %s
                    """
                ).format(
                    sql.Identifier(
                        self.document_table_name
                    )
                ),
                (
                    document_id,
                    tenant_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return DocumentVersionState(
            document_id=str(row[0]),
            tenant_id=str(row[1]),
            current_version=int(row[2]),
            created_at=row[3],
            updated_at=row[4],
        )

    def list_versions(
        self,
        *,
        document_id: str,
        tenant_id: str,
    ) -> list[DocumentVersion]:
        with psycopg.connect(
            self.database_url
        ) as connection:
            rows = connection.execute(
                sql.SQL(
                    """
                    SELECT
                        version_id,
                        document_id,
                        tenant_id,
                        version_number,
                        content_hash,
                        created_at
                    FROM {}
                    WHERE document_id = %s
                      AND tenant_id = %s
                    ORDER BY version_number
                    """
                ).format(
                    sql.Identifier(
                        self.version_table_name
                    )
                ),
                (
                    document_id,
                    tenant_id,
                ),
            ).fetchall()

        return [
            DocumentVersion(
                version_id=str(row[0]),
                document_id=str(row[1]),
                tenant_id=str(row[2]),
                version_number=int(row[3]),
                content_hash=str(row[4]),
                created_at=row[5],
            )
            for row in rows
        ]

    def drop_schema(self) -> None:
        with psycopg.connect(
            self.database_url,
            autocommit=True,
        ) as connection:
            connection.execute(
                sql.SQL(
                    "DROP TABLE IF EXISTS {}"
                ).format(
                    sql.Identifier(
                        self.version_table_name
                    )
                )
            )

            connection.execute(
                sql.SQL(
                    "DROP TABLE IF EXISTS {}"
                ).format(
                    sql.Identifier(
                        self.document_table_name
                    )
                )
            )
