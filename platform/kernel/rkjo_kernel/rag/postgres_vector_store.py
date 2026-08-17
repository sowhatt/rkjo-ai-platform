"""PostgreSQL/pgvector implementation of the RAG vector store."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector
from psycopg import sql
from psycopg.types.json import Jsonb

from rkjo_kernel.rag.models import (
    DocumentChunk,
    RetrievedChunk,
)
from rkjo_kernel.rag.embedding_space import (
    EmbeddingSpace,
)
from rkjo_kernel.rag.vector_store import VectorStore
from rkjo_kernel.rag.retrieval_filters import (
    RetrievalFilters,
)


class PostgresPgVectorStore(VectorStore):
    """Persistent vector store backed by PostgreSQL and pgvector."""

    def __init__(
        self,
        *,
        database_url: str,
        dimensions: int,
        table_name: str = "rag_chunks",
        embedding_space: EmbeddingSpace | None = None,
    ) -> None:
        if not database_url.strip():
            raise ValueError(
                "database_url must not be empty."
            )

        if dimensions <= 0:
            raise ValueError(
                "dimensions must be greater than 0."
            )

        if not table_name.strip():
            raise ValueError(
                "table_name must not be empty."
            )

        self.database_url = database_url
        self.dimensions = dimensions
        self.table_name = table_name.strip()
        self.embedding_space = embedding_space

        if (
            embedding_space is not None
            and embedding_space.dimensions != dimensions
        ):
            raise ValueError(
                "Embedding-space dimensions must match "
                "store dimensions."
            )

    def initialize_schema(self) -> None:
        """Enable pgvector and create the persistent chunk table."""

        with psycopg.connect(
            self.database_url,
            autocommit=True,
        ) as connection:
            connection.execute(
                "CREATE EXTENSION IF NOT EXISTS vector"
            )

            register_vector(
                connection
            )

            table = sql.Identifier(
                self.table_name
            )

            connection.execute(
                sql.SQL(
                    """
                    CREATE TABLE IF NOT EXISTS {} (
                        chunk_id TEXT PRIMARY KEY,
                        document_id TEXT NOT NULL,
                        content TEXT NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        metadata JSONB NOT NULL
                            DEFAULT '{{}}'::jsonb,
                        embedding vector({}) NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL
                            DEFAULT NOW()
                    )
                    """
                ).format(
                    table,
                    sql.SQL(
                        str(self.dimensions)
                    ),
                )
            )

            # Backward-compatible embedding-space migration.
            #
            # Existing rows remain NULL and therefore become legacy
            # vectors. They are never silently treated as belonging
            # to the currently configured embedding space.
            connection.execute(
                sql.SQL(
                    """
                    ALTER TABLE {}
                    ADD COLUMN IF NOT EXISTS
                        embedding_provider TEXT,
                    ADD COLUMN IF NOT EXISTS
                        embedding_model TEXT,
                    ADD COLUMN IF NOT EXISTS
                        embedding_dimensions INTEGER
                    """
                ).format(table)
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
                    table,
                )
            )

            space_index = sql.Identifier(
                f"{self.table_name}_embedding_space_idx"
            )

            connection.execute(
                sql.SQL(
                    """
                    CREATE INDEX IF NOT EXISTS {}
                    ON {} (
                        embedding_provider,
                        embedding_model,
                        embedding_dimensions
                    )
                    """
                ).format(
                    space_index,
                    table,
                )
            )

            vector_index = sql.Identifier(
                f"{self.table_name}_embedding_hnsw_idx"
            )

            connection.execute(
                sql.SQL(
                    """
                    CREATE INDEX IF NOT EXISTS {}
                    ON {}
                    USING hnsw (
                        embedding vector_cosine_ops
                    )
                    """
                ).format(
                    vector_index,
                    table,
                )
            )

    def add(
        self,
        *,
        chunk: DocumentChunk,
        embedding: list[float],
    ) -> None:
        """Insert or update one embedded document chunk."""

        self._validate_embedding(
            embedding
        )

        with self._connect() as connection:
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
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    ON CONFLICT (chunk_id)
                    DO UPDATE SET
                        document_id = EXCLUDED.document_id,
                        content = EXCLUDED.content,
                        chunk_index = EXCLUDED.chunk_index,
                        metadata = EXCLUDED.metadata,
                        embedding = EXCLUDED.embedding,
                        embedding_provider =
                            EXCLUDED.embedding_provider,
                        embedding_model =
                            EXCLUDED.embedding_model,
                        embedding_dimensions =
                            EXCLUDED.embedding_dimensions
                    """
                ).format(
                    sql.Identifier(
                        self.table_name
                    )
                ),
                (
                    chunk.chunk_id,
                    chunk.document_id,
                    chunk.content,
                    chunk.chunk_index,
                    Jsonb(
                        chunk.metadata
                    ),
                    Vector(
                        embedding
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

    def search(
        self,
        *,
        query_embedding: list[float],
        limit: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> list[RetrievedChunk]:
        """Return nearest chunks using cosine similarity."""

        self._validate_embedding(
            query_embedding
        )

        if limit <= 0:
            raise ValueError(
                "Search limit must be greater than 0."
            )

        query_vector = Vector(
            query_embedding
        )

        metadata_filter = Jsonb(
            (
                filters.metadata
                if filters is not None
                else {}
            )
        )

        with self._connect() as connection:
            if self.embedding_space is None:
                rows = connection.execute(
                    sql.SQL(
                        """
                        SELECT
                            chunk_id,
                            document_id,
                            content,
                            chunk_index,
                            metadata,
                            1 - (
                                embedding <=> %s
                            ) AS score
                        FROM {}
                        WHERE
                            metadata @> %s
                        ORDER BY
                            embedding <=> %s
                        LIMIT %s
                        """
                    ).format(
                        sql.Identifier(
                            self.table_name
                        )
                    ),
                    (
                        query_vector,
                        metadata_filter,
                        query_vector,
                        limit,
                    ),
                ).fetchall()

            else:
                rows = connection.execute(
                    sql.SQL(
                        """
                        SELECT
                            chunk_id,
                            document_id,
                            content,
                            chunk_index,
                            metadata,
                            1 - (
                                embedding <=> %s
                            ) AS score
                        FROM {}
                        WHERE
                            embedding_provider = %s
                            AND embedding_model = %s
                            AND embedding_dimensions = %s
                            AND metadata @> %s
                        ORDER BY
                            embedding <=> %s
                        LIMIT %s
                        """
                    ).format(
                        sql.Identifier(
                            self.table_name
                        )
                    ),
                    (
                        query_vector,
                        self.embedding_space.provider,
                        self.embedding_space.model,
                        self.embedding_space.dimensions,
                        metadata_filter,
                        query_vector,
                        limit,
                    ),
                ).fetchall()

        return [
            self._row_to_result(
                row
            )
            for row in rows
        ]

    def delete_document(
        self,
        document_id: str,
    ) -> int:
        """Delete every chunk belonging to one document."""

        if not document_id.strip():
            raise ValueError(
                "document_id must not be empty."
            )

        with self._connect() as connection:
            cursor = connection.execute(
                sql.SQL(
                    """
                    DELETE FROM {}
                    WHERE document_id = %s
                    """
                ).format(
                    sql.Identifier(
                        self.table_name
                    )
                ),
                (
                    document_id,
                ),
            )

            return cursor.rowcount

    def count(self) -> int:
        """Return number of persisted chunks."""

        with self._connect() as connection:
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

        if row is None:
            return 0

        return int(
            row[0]
        )

    def drop_schema(self) -> None:
        """Drop the backing table.

        Intended mainly for isolated integration tests.
        """

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

    def _connect(
        self,
    ) -> psycopg.Connection:
        connection = psycopg.connect(
            self.database_url,
            autocommit=True,
        )

        register_vector(
            connection
        )

        return connection

    def _validate_embedding(
        self,
        embedding: Sequence[float],
    ) -> None:
        if not embedding:
            raise ValueError(
                "Embedding must not be empty."
            )

        if (
            len(embedding)
            != self.dimensions
        ):
            raise ValueError(
                "Embedding dimensions must match "
                f"store dimensions ({self.dimensions})."
            )

    @staticmethod
    def _row_to_result(
        row: tuple[Any, ...],
    ) -> RetrievedChunk:
        chunk = DocumentChunk(
            chunk_id=str(
                row[0]
            ),
            document_id=str(
                row[1]
            ),
            content=str(
                row[2]
            ),
            chunk_index=int(
                row[3]
            ),
            metadata=dict(
                row[4] or {}
            ),
        )

        return RetrievedChunk(
            chunk=chunk,
            score=float(
                row[5]
            ),
        )
