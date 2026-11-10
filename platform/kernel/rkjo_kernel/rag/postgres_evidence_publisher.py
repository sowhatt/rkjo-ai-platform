"""Atomic, tenant-scoped PostgreSQL publication for MM-RAG evidence.

Do not use per-chunk VectorStore.add: all chunks become visible at commit.
The existing rag_chunks table must already be initialized.
"""
from __future__ import annotations

import hashlib

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector
from psycopg import sql
from psycopg.types.json import Jsonb

from rkjo_kernel.rag.evidence_ingestion import PreparedEvidence
from rkjo_kernel.rag.embedding_space import EmbeddingSpace


class PostgresEvidencePublisher:
    def __init__(
        self, *, database_url: str, table_name: str = "rag_chunks",
        embedding_space: EmbeddingSpace | None = None,
    ) -> None:
        if not database_url.strip() or not table_name.strip():
            raise ValueError("Database URL and table name are required.")
        self.database_url = database_url
        self.table_name = table_name
        self.embedding_space = embedding_space

    def publish(self, prepared: PreparedEvidence, *, tenant_id: str) -> int:
        """Replace one tenant's evidence atomically; refuse cross-tenant ID reuse.

        Advisory lock serializes publishers for a document including first insert.
        """
        if not tenant_id.strip() or tenant_id != prepared.tenant_id:
            raise PermissionError("Authorized tenant mismatch.")
        if not prepared.document_id.strip() or not prepared.chunks:
            raise ValueError("Document and chunks required.")
        for item in prepared.chunks:
            if (item.chunk.document_id != prepared.document_id
                or item.chunk.metadata.get("tenant_id") != tenant_id
                or item.chunk.metadata.get("evidence_document_id") != prepared.document_id):
                raise ValueError("Prepared chunk provenance mismatch.")
            if self.embedding_space is not None and len(item.embedding) != self.embedding_space.dimensions:
                raise ValueError("Prepared embedding dimensions mismatch.")

        table = sql.Identifier(self.table_name)
        lock_key = int.from_bytes(
            hashlib.sha256(prepared.document_id.encode("utf-8")).digest()[:8],
            byteorder="big", signed=True,
        )
        with psycopg.connect(self.database_url) as conn:
            register_vector(conn)
            with conn.transaction():
                conn.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key,))
                # A document_id must not refer to two tenants in this table.
                # The lock prevents concurrent publishers for the same ID.
                existing = conn.execute(
                    sql.SQL("SELECT metadata->>'tenant_id' FROM {} WHERE document_id = %s FOR UPDATE").format(table),
                    (prepared.document_id,),
                ).fetchall()
                if any(row[0] != tenant_id for row in existing):
                    raise PermissionError("Document ID already belongs to a different tenant.")
                conn.execute(
                    sql.SQL("DELETE FROM {} WHERE document_id = %s AND metadata->>'tenant_id' = %s").format(table),
                    (prepared.document_id, tenant_id),
                )
                for item in prepared.chunks:
                    conn.execute(
                        sql.SQL("""
                            INSERT INTO {} (
                                chunk_id, document_id, content, chunk_index,
                                metadata, embedding,
                                embedding_provider, embedding_model, embedding_dimensions
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """).format(table),
                        (
                            item.chunk.chunk_id, item.chunk.document_id,
                            item.chunk.content, item.chunk.chunk_index,
                            Jsonb(item.chunk.metadata), Vector(list(item.embedding)),
                            self.embedding_space.provider if self.embedding_space else None,
                            self.embedding_space.model if self.embedding_space else None,
                            self.embedding_space.dimensions if self.embedding_space else None,
                        ),
                    )
        return len(prepared.chunks)
