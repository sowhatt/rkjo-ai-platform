"""Atomic PostgreSQL RAG document replacement."""

from __future__ import annotations

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
        self.embedding_space = embedding_space

    def replace(
        self,
        prepared: PreparedIngestion,
        *,
        filters: RetrievalFilters | None = None,
    ) -> tuple[int, int] | None:
        """Atomically replace chunks and deduplication hash."""

        metadata_filter = Jsonb(
            (
                filters.metadata
                if filters is not None
                else {}
            )
        )

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
