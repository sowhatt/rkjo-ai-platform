"""PostgreSQL full-text lexical retrieval for RKJO RAG."""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg import sql

from rkjo_kernel.rag.embedding_space import (
    EmbeddingSpace,
)
from rkjo_kernel.rag.models import (
    DocumentChunk,
    RetrievedChunk,
)


class PostgresLexicalRetriever:
    """Retrieve chunks using PostgreSQL full-text search."""

    def __init__(
        self,
        *,
        database_url: str,
        table_name: str = "rag_chunks",
        embedding_space: EmbeddingSpace | None = None,
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
        self.embedding_space = embedding_space

    def initialize_schema(self) -> None:
        """Create an expression GIN index for lexical retrieval."""

        with psycopg.connect(
            self.database_url,
            autocommit=True,
        ) as connection:
            index = sql.Identifier(
                f"{self.table_name}_content_fts_idx"
            )

            table = sql.Identifier(
                self.table_name
            )

            connection.execute(
                sql.SQL(
                    """
                    CREATE INDEX IF NOT EXISTS {}
                    ON {}
                    USING GIN (
                        to_tsvector(
                            'simple'::regconfig,
                            content
                        )
                    )
                    """
                ).format(
                    index,
                    table,
                )
            )

    def retrieve(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> list[RetrievedChunk]:
        if not query.strip():
            raise ValueError(
                "Lexical query must not be empty."
            )

        if limit <= 0:
            raise ValueError(
                "Lexical retrieval limit must be "
                "greater than 0."
            )

        table = sql.Identifier(
            self.table_name
        )

        with psycopg.connect(
            self.database_url,
            autocommit=True,
        ) as connection:
            if self.embedding_space is None:
                rows = connection.execute(
                    sql.SQL(
                        """
                        WITH lexical_query AS (
                            SELECT
                                websearch_to_tsquery(
                                    'simple'::regconfig,
                                    %s
                                ) AS query
                        )
                        SELECT
                            chunk_id,
                            document_id,
                            content,
                            chunk_index,
                            metadata,
                            ts_rank_cd(
                                to_tsvector(
                                    'simple'::regconfig,
                                    content
                                ),
                                lexical_query.query
                            ) AS score
                        FROM {},
                             lexical_query
                        WHERE
                            to_tsvector(
                                'simple'::regconfig,
                                content
                            )
                            @@ lexical_query.query
                        ORDER BY
                            score DESC,
                            chunk_id ASC
                        LIMIT %s
                        """
                    ).format(table),
                    (
                        query,
                        limit,
                    ),
                ).fetchall()

            else:
                rows = connection.execute(
                    sql.SQL(
                        """
                        WITH lexical_query AS (
                            SELECT
                                websearch_to_tsquery(
                                    'simple'::regconfig,
                                    %s
                                ) AS query
                        )
                        SELECT
                            chunk_id,
                            document_id,
                            content,
                            chunk_index,
                            metadata,
                            ts_rank_cd(
                                to_tsvector(
                                    'simple'::regconfig,
                                    content
                                ),
                                lexical_query.query
                            ) AS score
                        FROM {},
                             lexical_query
                        WHERE
                            to_tsvector(
                                'simple'::regconfig,
                                content
                            )
                            @@ lexical_query.query
                            AND embedding_provider = %s
                            AND embedding_model = %s
                            AND embedding_dimensions = %s
                        ORDER BY
                            score DESC,
                            chunk_id ASC
                        LIMIT %s
                        """
                    ).format(table),
                    (
                        query,
                        self.embedding_space.provider,
                        self.embedding_space.model,
                        self.embedding_space.dimensions,
                        limit,
                    ),
                ).fetchall()

        return [
            self._row_to_result(row)
            for row in rows
        ]

    @staticmethod
    def _row_to_result(
        row: tuple[Any, ...],
    ) -> RetrievedChunk:
        return RetrievedChunk(
            chunk=DocumentChunk(
                chunk_id=str(row[0]),
                document_id=str(row[1]),
                content=str(row[2]),
                chunk_index=int(row[3]),
                metadata=dict(
                    row[4] or {}
                ),
            ),
            score=float(row[5]),
        )
