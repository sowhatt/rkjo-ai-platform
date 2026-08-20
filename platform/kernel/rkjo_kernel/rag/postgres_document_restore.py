from __future__ import annotations

from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from pgvector import Vector
from pgvector.psycopg import register_vector

from rkjo_kernel.rag.document_restore import (
    DocumentRestoreResult,
)
from rkjo_kernel.rag.embedding_space import (
    EmbeddingSpace,
)


class PostgresDocumentRestoreRepository:
    """Atomically restore an archived document version.

    Restore never rewinds version numbering. Restoring v1 while
    v3 is current creates a new v4 whose content is derived from v1.
    """

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
        embedding_space: EmbeddingSpace,
    ) -> None:
        self.database_url = database_url
        self.chunk_table_name = chunk_table_name
        self.hash_table_name = hash_table_name
        self.document_table_name = document_table_name
        self.version_table_name = version_table_name
        self.version_chunk_table_name = (
            version_chunk_table_name
        )
        self.embedding_space = embedding_space

    def restore(
        self,
        *,
        document_id: str,
        tenant_id: str,
        version_number: int,
    ) -> DocumentRestoreResult:
        if version_number < 1:
            raise ValueError(
                "version_number must be >= 1."
            )

        with psycopg.connect(
            self.database_url
        ) as connection:
            register_vector(connection)

            documents = sql.Identifier(
                self.document_table_name
            )
            versions = sql.Identifier(
                self.version_table_name
            )
            snapshots = sql.Identifier(
                self.version_chunk_table_name
            )
            chunks = sql.Identifier(
                self.chunk_table_name
            )
            hashes = sql.Identifier(
                self.hash_table_name
            )

            # Serialize all lifecycle operations for this document.
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
                raise LookupError(
                    "Document not found."
                )

            current_version = int(state[0])

            if version_number == current_version:
                raise ValueError(
                    "Cannot restore the current version."
                )

            source = connection.execute(
                sql.SQL(
                    """
                    SELECT
                        version_id,
                        content_hash
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
                    version_number,
                ),
            ).fetchone()

            if source is None:
                raise LookupError(
                    "Document version not found."
                )

            source_version_id = str(
                source[0]
            )
            source_content_hash = str(
                source[1]
            )

            source_chunks = connection.execute(
                sql.SQL(
                    """
                    SELECT
                        chunk_id,
                        chunk_index,
                        content,
                        metadata,
                        embedding,
                        embedding_provider,
                        embedding_model,
                        embedding_dimensions
                    FROM {}
                    WHERE version_id = %s
                      AND document_id = %s
                      AND tenant_id = %s
                    ORDER BY chunk_index
                    FOR UPDATE
                    """
                ).format(snapshots),
                (
                    source_version_id,
                    document_id,
                    tenant_id,
                ),
            ).fetchall()

            if not source_chunks:
                raise LookupError(
                    "Document version snapshot not found."
                )

            # Validate embedding compatibility before touching
            # the current active version.
            for row in source_chunks:
                provider = (
                    str(row[5])
                    if row[5] is not None
                    else None
                )
                model = (
                    str(row[6])
                    if row[6] is not None
                    else None
                )
                dimensions = (
                    int(row[7])
                    if row[7] is not None
                    else None
                )

                if (
                    provider
                    != self.embedding_space.provider
                    or model
                    != self.embedding_space.model
                    or dimensions
                    != self.embedding_space.dimensions
                ):
                    raise ValueError(
                        "Historical embedding space is "
                        "incompatible with the active "
                        "embedding space."
                    )

            current = connection.execute(
                sql.SQL(
                    """
                    SELECT
                        version_id,
                        content_hash
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

            if current is None:
                raise RuntimeError(
                    "Current document version metadata "
                    "is missing."
                )

            current_version_id = str(
                current[0]
            )

            # Archive the currently active chunks before deletion.
            active_chunks = connection.execute(
                sql.SQL(
                    """
                    SELECT
                        chunk_id,
                        chunk_index,
                        content,
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
                ).format(chunks),
                (
                    document_id,
                    Jsonb(
                        {
                            "tenant_id": tenant_id
                        }
                    ),
                ),
            ).fetchall()

            if not active_chunks:
                raise RuntimeError(
                    "Current document has no active chunks."
                )

            already_archived = connection.execute(
                sql.SQL(
                    """
                    SELECT 1
                    FROM {}
                    WHERE version_id = %s
                    LIMIT 1
                    """
                ).format(snapshots),
                (current_version_id,),
            ).fetchone()

            if already_archived is not None:
                raise RuntimeError(
                    "Current document version snapshot "
                    "already exists."
                )

            for row in active_chunks:
                raw_embedding = row[4]

                if isinstance(
                    raw_embedding,
                    Vector,
                ):
                    embedding = (
                        raw_embedding.to_list()
                    )
                else:
                    embedding = list(
                        raw_embedding
                    )

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
                    ).format(snapshots),
                    (
                        current_version_id,
                        document_id,
                        tenant_id,
                        str(row[0]),
                        int(row[1]),
                        str(row[2]),
                        Jsonb(dict(row[3])),
                        [
                            float(value)
                            for value in embedding
                        ],
                        (
                            str(row[5])
                            if row[5] is not None
                            else None
                        ),
                        (
                            str(row[6])
                            if row[6] is not None
                            else None
                        ),
                        (
                            int(row[7])
                            if row[7] is not None
                            else None
                        ),
                    ),
                )

            # Remove current active representation.
            connection.execute(
                sql.SQL(
                    """
                    DELETE FROM {}
                    WHERE document_id = %s
                      AND metadata @> %s
                    """
                ).format(chunks),
                (
                    document_id,
                    Jsonb(
                        {
                            "tenant_id": tenant_id
                        }
                    ),
                ),
            )

            connection.execute(
                sql.SQL(
                    """
                    DELETE FROM {}
                    WHERE document_id = %s
                    """
                ).format(hashes),
                (document_id,),
            )

            new_version = (
                current_version + 1
            )
            new_version_id = str(
                uuid4()
            )

            # Restored chunks become a new active representation.
            # Generate new chunk IDs: historical snapshots remain
            # immutable and keep their original IDs.
            for row in source_chunks:
                raw_embedding = row[4]

                embedding_values = [
                    float(value)
                    for value in raw_embedding
                ]

                metadata = dict(
                    row[3]
                )

                metadata[
                    "tenant_id"
                ] = tenant_id
                metadata[
                    "content_hash"
                ] = source_content_hash
                metadata[
                    "restored_from_version"
                ] = version_number

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
                    ).format(chunks),
                    (
                        str(uuid4()),
                        document_id,
                        str(row[2]),
                        int(row[1]),
                        Jsonb(metadata),
                        Vector(
                            embedding_values
                        ),
                        str(row[5]),
                        str(row[6]),
                        int(row[7]),
                    ),
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
                ).format(hashes),
                (
                    source_content_hash,
                    document_id,
                ),
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
                    new_version_id,
                    document_id,
                    tenant_id,
                    new_version,
                    source_content_hash,
                ),
            )

            connection.execute(
                sql.SQL(
                    """
                    UPDATE {}
                    SET current_version = %s,
                        updated_at = NOW()
                    WHERE document_id = %s
                      AND tenant_id = %s
                    """
                ).format(documents),
                (
                    new_version,
                    document_id,
                    tenant_id,
                ),
            )

            return DocumentRestoreResult(
                document_id=document_id,
                restored_from_version=version_number,
                new_version=new_version,
                content_hash=source_content_hash,
                chunk_count=len(
                    source_chunks
                ),
            )
