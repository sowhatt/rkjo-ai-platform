import os
import uuid

import psycopg

from rkjo_kernel.rag.embedding_space import (
    EmbeddingSpace,
)
from rkjo_kernel.rag.ingestion_models import (
    PreparedChunk,
    PreparedIngestion,
)
from rkjo_kernel.rag.models import DocumentChunk
from rkjo_kernel.rag.postgres_deduplication import (
    PostgresDocumentHashRegistry,
)
from rkjo_kernel.rag.postgres_document_replacement import (
    PostgresDocumentReplacementRepository,
)
from rkjo_kernel.rag.postgres_document_restore import (
    PostgresDocumentRestoreRepository,
)
from rkjo_kernel.rag.postgres_document_versioning import (
    PostgresDocumentVersionRepository,
)
from rkjo_kernel.rag.postgres_vector_store import (
    PostgresPgVectorStore,
)
from rkjo_kernel.rag.retrieval_filters import (
    RetrievalFilters,
)


DATABASE_URL = os.getenv(
    "RKJO_TEST_DATABASE_URL",
    "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
)


def prepared(content, content_hash):
    return PreparedIngestion(
        document_id="doc-restore",
        content_hash=content_hash,
        chunks=(
            PreparedChunk(
                chunk=DocumentChunk(
                    document_id="doc-restore",
                    chunk_id=str(uuid.uuid4()),
                    content=content,
                    chunk_index=0,
                    metadata={
                        "tenant_id": "tenant-a",
                        "content_hash": content_hash,
                    },
                ),
                embedding=(1.0, 0.0, 0.0),
            ),
        ),
    )


def test_restore_creates_new_current_version():
    suffix = uuid.uuid4().hex[:10]

    chunk_table = f"rag_restore_chunks_{suffix}"
    hash_table = f"rag_restore_hashes_{suffix}"
    document_table = f"rag_restore_docs_{suffix}"
    version_table = f"rag_restore_versions_{suffix}"
    snapshot_table = f"rag_restore_snapshots_{suffix}"

    space = EmbeddingSpace(
        provider="openai",
        model="restore-model",
        dimensions=3,
    )

    store = PostgresPgVectorStore(
        database_url=DATABASE_URL,
        dimensions=3,
        table_name=chunk_table,
        embedding_space=space,
    )

    hashes = PostgresDocumentHashRegistry(
        database_url=DATABASE_URL,
        table_name=hash_table,
    )

    versions = PostgresDocumentVersionRepository(
        database_url=DATABASE_URL,
        document_table_name=document_table,
        version_table_name=version_table,
        version_chunk_table_name=snapshot_table,
    )

    replacement = PostgresDocumentReplacementRepository(
        database_url=DATABASE_URL,
        chunk_table_name=chunk_table,
        hash_table_name=hash_table,
        document_table_name=document_table,
        version_table_name=version_table,
        version_chunk_table_name=snapshot_table,
        embedding_space=space,
    )

    restore = PostgresDocumentRestoreRepository(
        database_url=DATABASE_URL,
        chunk_table_name=chunk_table,
        hash_table_name=hash_table,
        document_table_name=document_table,
        version_table_name=version_table,
        version_chunk_table_name=snapshot_table,
        embedding_space=space,
    )

    store.initialize_schema()
    hashes.initialize_schema()
    versions.initialize_schema()

    try:
        hash_v1 = "a" * 64
        hash_v2 = "b" * 64
        hash_v3 = "c" * 64

        store.add(
            chunk=DocumentChunk(
                document_id="doc-restore",
                chunk_id="v1-chunk",
                content="content version one",
                chunk_index=0,
                metadata={
                    "tenant_id": "tenant-a",
                    "content_hash": hash_v1,
                },
            ),
            embedding=[1.0, 0.0, 0.0],
        )

        hashes.register(
            content_hash=hash_v1,
            document_id="doc-restore",
        )

        filters = RetrievalFilters(
            metadata={
                "tenant_id": "tenant-a"
            }
        )

        replacement.replace(
            prepared(
                "content version two",
                hash_v2,
            ),
            filters=filters,
        )

        replacement.replace(
            prepared(
                "content version three",
                hash_v3,
            ),
            filters=filters,
        )

        result = restore.restore(
            document_id="doc-restore",
            tenant_id="tenant-a",
            version_number=1,
        )

        assert result.restored_from_version == 1
        assert result.new_version == 4
        assert result.content_hash == hash_v1
        assert result.chunk_count == 1

        history = versions.list_versions(
            document_id="doc-restore",
            tenant_id="tenant-a",
        )

        assert [
            item.version_number
            for item in history
        ] == [1, 2, 3, 4]

        assert history[-1].content_hash == hash_v1

        with psycopg.connect(
            DATABASE_URL
        ) as connection:
            active = connection.execute(
                f"""
                SELECT
                    content,
                    metadata->>'tenant_id',
                    metadata->>'restored_from_version'
                FROM {chunk_table}
                WHERE document_id = %s
                """,
                ("doc-restore",),
            ).fetchall()

        assert len(active) == 1
        assert active[0][0] == "content version one"
        assert active[0][1] == "tenant-a"
        assert active[0][2] == "1"

        v3_chunks = versions.list_version_chunks(
            document_id="doc-restore",
            tenant_id="tenant-a",
            version_id=history[2].version_id,
        )

        assert len(v3_chunks) == 1
        assert (
            v3_chunks[0].content
            == "content version three"
        )

    finally:
        store.drop_schema()
        hashes.drop_schema()
        versions.drop_schema()
