"""Atomic PostgreSQL RAG document replacement."""

from __future__ import annotations

from uuid import uuid4

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector
from psycopg import sql
from psycopg.types.json import Jsonb

from rkjo_kernel.rag.embedding_space import (
    EmbeddingSpace,
)
from rkjo_kernel.rag.ingestion_models import (
    PreparedIngestion,
)
from rkjo_kernel.rag.retrieval_filters import (
    RetrievalFilters,
)


class PostgresDocumentReplacementRepository:
    """Atomically swap all persisted state for one document."""

    def __init__(
        self,
        *,
        database_url: str,
        chunk_table_name: str = "rag_chunks",
        hash_table_name: str = "rag_document_hashes",
        document_table_name: str = "rag_documents",
        version_table_name: str = "rag_document_versions",
        version_chunk_table_name: str = (
            "rag_document_version_chunks"
        ),
        embedding_space: EmbeddingSpace | None = None,
    ) -> None:
        if not database_url.strip():
            raise ValueError(
                "database_url must not be empty."
            )

        self.database_url = database_url
        self.chunk_table_name = (
            chunk_table_name.strip()
        )
        self.hash_table_name = (
            hash_table_name.strip()
        )
        self.document_table_name = (
            document_table_name.strip()
        )
        self.version_table_name = (
            version_table_name.strip()
        )
        self.version_chunk_table_name = (
            version_chunk_table_name.strip()
        )
        self.embedding_space = embedding_space

    def replace(
        self,
        prepared: PreparedIngestion,
        *,
        filters: RetrievalFilters | None = None,
    ) -> tuple[int, int] | None:
        """Atomically replace chunks and deduplication hash."""

        filter_metadata = (
            filters.metadata
            if filters is not None
            else {}
        )

        metadata_filter = Jsonb(
            filter_metadata
        )

        tenant_id = filter_metadata.get(
            "tenant_id"
        )

        if not isinstance(
            tenant_id,
            str,
        ) or not tenant_id.strip():
            raise ValueError(
                "Tenant-scoped replacement requires tenant_id."
            )

        tenant_id = tenant_id.strip()

        with psycopg.connect(
            self.database_url
        ) as connection:
            register_vector(connection)

            # Connection context commits on success and rolls
            # back automatically on exception.
            with connection.transaction():
                existing_rows = connection.execute(
                    sql.SQL(
                        """
                        SELECT chunk_id
                        FROM {}
                        WHERE document_id = %s
                          AND metadata @> %s
                        FOR UPDATE
                        """
                    ).format(
                        sql.Identifier(
                            self.chunk_table_name
                        )
                    ),
                    (
                        prepared.document_id,
                        metadata_filter,
                    ),
                ).fetchall()

                if not existing_rows:
                    return None

                old_hash_row = connection.execute(
                    sql.SQL(
                        """
                        SELECT content_hash
                        FROM {}
                        WHERE document_id = %s
                        LIMIT 1
                        FOR UPDATE
                        """
                    ).format(
                        sql.Identifier(
                            self.hash_table_name
                        )
                    ),
                    (
                        prepared.document_id,
                    ),
                ).fetchone()

                if old_hash_row is None:
                    raise RuntimeError(
                        "Existing document has no registered hash."
                    )

                old_content_hash = str(
                    old_hash_row[0]
                )

                duplicate = connection.execute(
                    sql.SQL(
                        """
                        SELECT document_id
                        FROM {}
                        WHERE content_hash = %s
                        LIMIT 1
                        FOR UPDATE
                        """
                    ).format(
                        sql.Identifier(
                            self.hash_table_name
                        )
                    ),
                    (
                        prepared.content_hash,
                    ),
                ).fetchone()

                if duplicate is not None:
                    duplicate_document_id = str(
                        duplicate[0]
                    )

                    if (
                        duplicate_document_id
                        == prepared.document_id
                    ):
                        raise ValueError(
                            "Replacement content is "
                            "identical to current document."
                        )

                    raise ValueError(
                        "Replacement content duplicates "
                        "an existing document."
                    )

                self._register_versions(
                    connection,
                    document_id=prepared.document_id,
                    tenant_id=tenant_id,
                    old_content_hash=old_content_hash,
                    new_content_hash=prepared.content_hash,
                    metadata_filter=metadata_filter,
                )

                hash_cursor = connection.execute(
                    sql.SQL(
                        """
                        DELETE FROM {}
                        WHERE document_id = %s
                        """
                    ).format(
                        sql.Identifier(
                            self.hash_table_name
                        )
                    ),
                    (
                        prepared.document_id,
                    ),
                )

                chunk_cursor = connection.execute(
                    sql.SQL(
                        """
                        DELETE FROM {}
                        WHERE document_id = %s
                          AND metadata @> %s
                        """
                    ).format(
                        sql.Identifier(
                            self.chunk_table_name
                        )
                    ),
                    (
                        prepared.document_id,
                        metadata_filter,
                    ),
                )

                deleted_chunks = (
                    chunk_cursor.rowcount
                )
                deleted_hashes = (
                    hash_cursor.rowcount
                )

                self._insert_chunks(
                    connection,
                    prepared,
                )

                connection.execute(
                    sql.SQL(
                        """
                        INSERT INTO {} (
                            content_hash,
                            document_id
                        )
                        VALUES (%s, %s)
                        """
                    ).format(
                        sql.Identifier(
                            self.hash_table_name
                        )
                    ),
                    (
                        prepared.content_hash,
                        prepared.document_id,
                    ),
                )

                return (
                    deleted_chunks,
                    deleted_hashes,
                )

    def _insert_chunks(
        self,
        connection,
        prepared: PreparedIngestion,
    ) -> None:
        """Insert prepared chunks inside caller transaction."""

        for item in prepared.chunks:
            connection.execute(
                sql.SQL(
                    """
                    INSERT INTO {} (
                        chunk_id,
                        document_id,
                        content,
                        chunk_index,
                        metadata,
                        embedding,
                        embedding_provider,
                        embedding_model,
                        embedding_dimensions
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s
                    )
                    """
                ).format(
                    sql.Identifier(
                        self.chunk_table_name
                    )
                ),
                (
                    item.chunk.chunk_id,
                    item.chunk.document_id,
                    item.chunk.content,
                    item.chunk.chunk_index,
                    Jsonb(
                        item.chunk.metadata
                    ),
                    Vector(
                        list(
                            item.embedding
                        )
                    ),
                    (
                        self.embedding_space.provider
                        if self.embedding_space
                        else None
                    ),
                    (
                        self.embedding_space.model
                        if self.embedding_space
                        else None
                    ),
                    (
                        self.embedding_space.dimensions
                        if self.embedding_space
                        else None
                    ),
                ),
            )


    def _register_versions(
        self,
        connection,
        *,
        document_id: str,
        tenant_id: str,
        old_content_hash: str,
        new_content_hash: str,
        metadata_filter: Jsonb,
    ) -> None:
        """Register historical/current version inside swap transaction."""

        documents = sql.Identifier(
            self.document_table_name
        )
        versions = sql.Identifier(
            self.version_table_name
        )

        state = connection.execute(
            sql.SQL(
                """
                SELECT current_version
                FROM {}
                WHERE document_id = %s
                  AND tenant_id = %s
                FOR UPDATE
                """
            ).format(documents),
            (
                document_id,
                tenant_id,
            ),
        ).fetchone()

        if state is None:
            # First replacement:
            # current persisted document becomes v1.
            connection.execute(
                sql.SQL(
                    """
                    INSERT INTO {} (
                        document_id,
                        tenant_id,
                        current_version
                    )
                    VALUES (%s, %s, 2)
                    """
                ).format(documents),
                (
                    document_id,
                    tenant_id,
                ),
            )

            old_version_id = str(
                uuid4()
            )

            connection.execute(
                sql.SQL(
                    """
                    INSERT INTO {} (
                        version_id,
                        document_id,
                        tenant_id,
                        version_number,
                        content_hash
                    )
                    VALUES (%s, %s, %s, 1, %s)
                    """
                ).format(versions),
                (
                    old_version_id,
                    document_id,
                    tenant_id,
                    old_content_hash,
                ),
            )

            next_version = 2

        else:
            current_version = int(
                state[0]
            )

            old_version_row = (
                connection.execute(
                    sql.SQL(
                        """
                        SELECT version_id
                        FROM {}
                        WHERE document_id = %s
                          AND tenant_id = %s
                          AND version_number = %s
                        FOR UPDATE
                        """
                    ).format(versions),
                    (
                        document_id,
                        tenant_id,
                        current_version,
                    ),
                ).fetchone()
            )

            if old_version_row is None:
                raise RuntimeError(
                    "Current document version metadata is missing."
                )

            old_version_id = str(
                old_version_row[0]
            )

            next_version = (
                current_version + 1
            )

            connection.execute(
                sql.SQL(
                    """
                    UPDATE {}
                    SET
                        current_version = %s,
                        updated_at = NOW()
                    WHERE document_id = %s
                      AND tenant_id = %s
                    """
                ).format(documents),
                (
                    next_version,
                    document_id,
                    tenant_id,
                ),
            )

        self._snapshot_active_chunks(
            connection,
            version_id=old_version_id,
            document_id=document_id,
            tenant_id=tenant_id,
            metadata_filter=metadata_filter,
        )

        connection.execute(
            sql.SQL(
                """
                INSERT INTO {} (
                    version_id,
                    document_id,
                    tenant_id,
                    version_number,
                    content_hash
                )
                VALUES (%s, %s, %s, %s, %s)
                """
            ).format(versions),
            (
                str(uuid4()),
                document_id,
                tenant_id,
                next_version,
                new_content_hash,
            ),
        )


    def _snapshot_active_chunks(
        self,
        connection,
        *,
        version_id: str,
        document_id: str,
        tenant_id: str,
        metadata_filter: Jsonb,
    ) -> None:
        """Archive active chunks before they are destructively replaced."""

        rows = connection.execute(
            sql.SQL(
                """
                SELECT
                    chunk_id,
                    document_id,
                    content,
                    chunk_index,
                    metadata,
                    embedding,
                    embedding_provider,
                    embedding_model,
                    embedding_dimensions
                FROM {}
                WHERE document_id = %s
                  AND metadata @> %s
                ORDER BY chunk_index
                FOR UPDATE
                """
            ).format(
                sql.Identifier(
                    self.chunk_table_name
                )
            ),
            (
                document_id,
                metadata_filter,
            ),
        ).fetchall()

        if not rows:
            raise RuntimeError(
                "Cannot snapshot a document without active chunks."
            )

        snapshot_table = sql.Identifier(
            self.version_chunk_table_name
        )

        # A version must be immutable. If a snapshot already
        # exists, replacement state is inconsistent.
        existing = connection.execute(
            sql.SQL(
                """
                SELECT 1
                FROM {}
                WHERE version_id = %s
                LIMIT 1
                """
            ).format(snapshot_table),
            (version_id,),
        ).fetchone()

        if existing is not None:
            raise RuntimeError(
                "Document version snapshot already exists."
            )

        for row in rows:
            raw_embedding = row[5]

            if isinstance(
                raw_embedding,
                Vector,
            ):
                embedding_values = (
                    raw_embedding.to_list()
                )
            else:
                embedding_values = (
                    raw_embedding
                )

            embedding = [
                float(value)
                for value in embedding_values
            ]

            connection.execute(
                sql.SQL(
                    """
                    INSERT INTO {} (
                        version_id,
                        document_id,
                        tenant_id,
                        chunk_id,
                        chunk_index,
                        content,
                        metadata,
                        embedding,
                        embedding_provider,
                        embedding_model,
                        embedding_dimensions
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s
                    )
                    """
                ).format(snapshot_table),
                (
                    version_id,
                    document_id,
                    tenant_id,
                    str(row[0]),
                    int(row[3]),
                    str(row[2]),
                    Jsonb(dict(row[4])),
                    embedding,
                    (
                        str(row[6])
                        if row[6] is not None
                        else None
                    ),
                    (
                        str(row[7])
                        if row[7] is not None
                        else None
                    ),
                    (
                        int(row[8])
                        if row[8] is not None
                        else None
                    ),
                ),
            )
