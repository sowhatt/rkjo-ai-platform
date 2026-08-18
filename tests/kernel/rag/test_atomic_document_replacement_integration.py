import os
import uuid

import pytest
import psycopg

from rkjo_kernel.rag.embedding_space import (
    EmbeddingSpace,
)
from rkjo_kernel.rag.ingestion_models import (
    PreparedChunk,
    PreparedIngestion,
)
from rkjo_kernel.rag.models import (
    DocumentChunk,
)
from rkjo_kernel.rag.postgres_deduplication import (
    PostgresDocumentHashRegistry,
)
from rkjo_kernel.rag.postgres_document_replacement import (
    PostgresDocumentReplacementRepository,
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


class FailingRepository(
    PostgresDocumentReplacementRepository
):
    def _insert_chunks(
        self,
        connection,
        prepared,
    ):
        raise RuntimeError(
            "simulated database failure"
        )


def build_prepared(
    document_id,
    content,
    content_hash,
):
    return PreparedIngestion(
        document_id=document_id,
        content_hash=content_hash,
        chunks=(
            PreparedChunk(
                chunk=DocumentChunk(
                    document_id=document_id,
                    chunk_id=str(uuid.uuid4()),
                    content=content,
                    chunk_index=0,
                    metadata={
                        "tenant_id": "tenant-a",
                        "content_hash": content_hash,
                    },
                ),
                embedding=(
                    0.0,
                    1.0,
                    0.0,
                ),
            ),
        ),
    )


def test_database_failure_rolls_back_old_document():
    suffix = uuid.uuid4().hex[:10]

    chunk_table = (
        f"rag_atomic_chunks_{suffix}"
    )
    hash_table = (
        f"rag_atomic_hashes_{suffix}"
    )
    document_table = (
        f"rag_atomic_documents_{suffix}"
    )
    version_table = (
        f"rag_atomic_versions_{suffix}"
    )

    space = EmbeddingSpace(
        provider="openai",
        model="test-model",
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
    )

    store.initialize_schema()
    hashes.initialize_schema()
    versions.initialize_schema()

    try:
        old_hash = "a" * 64

        store.add(
            chunk=DocumentChunk(
                document_id="doc-1",
                chunk_id="old-chunk",
                content="old version",
                chunk_index=0,
                metadata={
                    "tenant_id": "tenant-a",
                    "content_hash": old_hash,
                },
            ),
            embedding=[
                1.0,
                0.0,
                0.0,
            ],
        )

        hashes.register(
            content_hash=old_hash,
            document_id="doc-1",
        )

        repository = FailingRepository(
            database_url=DATABASE_URL,
            chunk_table_name=chunk_table,
            hash_table_name=hash_table,
            document_table_name=document_table,
            version_table_name=version_table,
            embedding_space=space,
        )

        with pytest.raises(
            RuntimeError,
            match="simulated database failure",
        ):
            repository.replace(
                build_prepared(
                    "doc-1",
                    "new version",
                    "b" * 64,
                ),
                filters=RetrievalFilters(
                    metadata={
                        "tenant_id": "tenant-a"
                    }
                ),
            )

        # Transaction rollback must restore V1.
        with psycopg.connect(
            DATABASE_URL
        ) as connection:
            chunk = connection.execute(
                f"""
                SELECT content
                FROM {chunk_table}
                WHERE document_id = %s
                """,
                ("doc-1",),
            ).fetchone()

            old_registry = connection.execute(
                f"""
                SELECT document_id
                FROM {hash_table}
                WHERE content_hash = %s
                """,
                (old_hash,),
            ).fetchone()

            new_registry = connection.execute(
                f"""
                SELECT document_id
                FROM {hash_table}
                WHERE content_hash = %s
                """,
                ("b" * 64,),
            ).fetchone()

        assert chunk is not None
        assert chunk[0] == "old version"
        assert old_registry is not None
        assert new_registry is None

    finally:
        store.drop_schema()
        hashes.drop_schema()
        versions.drop_schema()


def test_atomic_replace_commits_new_document():
    suffix = uuid.uuid4().hex[:10]

    chunk_table = (
        f"rag_atomic_chunks_{suffix}"
    )
    hash_table = (
        f"rag_atomic_hashes_{suffix}"
    )
    document_table = (
        f"rag_atomic_documents_{suffix}"
    )
    version_table = (
        f"rag_atomic_versions_{suffix}"
    )

    space = EmbeddingSpace(
        provider="openai",
        model="test-model",
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
    )

    store.initialize_schema()
    hashes.initialize_schema()
    versions.initialize_schema()

    try:
        old_hash = "a" * 64
        new_hash = "b" * 64

        store.add(
            chunk=DocumentChunk(
                document_id="doc-1",
                chunk_id="old-chunk",
                content="old version",
                chunk_index=0,
                metadata={
                    "tenant_id": "tenant-a",
                    "content_hash": old_hash,
                },
            ),
            embedding=[
                1.0,
                0.0,
                0.0,
            ],
        )

        hashes.register(
            content_hash=old_hash,
            document_id="doc-1",
        )

        repository = (
            PostgresDocumentReplacementRepository(
                database_url=DATABASE_URL,
                chunk_table_name=chunk_table,
                hash_table_name=hash_table,
                document_table_name=document_table,
                version_table_name=version_table,
                embedding_space=space,
            )
        )

        result = repository.replace(
            build_prepared(
                "doc-1",
                "new version",
                new_hash,
            ),
            filters=RetrievalFilters(
                metadata={
                    "tenant_id": "tenant-a"
                }
            ),
        )

        assert result == (1, 1)

        with psycopg.connect(
            DATABASE_URL
        ) as connection:
            chunk = connection.execute(
                f"""
                SELECT content
                FROM {chunk_table}
                WHERE document_id = %s
                """,
                ("doc-1",),
            ).fetchone()

            old_registry = connection.execute(
                f"""
                SELECT document_id
                FROM {hash_table}
                WHERE content_hash = %s
                """,
                (old_hash,),
            ).fetchone()

            new_registry = connection.execute(
                f"""
                SELECT document_id
                FROM {hash_table}
                WHERE content_hash = %s
                """,
                (new_hash,),
            ).fetchone()

        assert chunk[0] == "new version"
        assert old_registry is None
        assert new_registry is not None

    finally:
        store.drop_schema()
        hashes.drop_schema()
        versions.drop_schema()
