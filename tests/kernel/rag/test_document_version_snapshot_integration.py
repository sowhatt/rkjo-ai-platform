import os
import uuid

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


def prepared(
    *,
    document_id,
    content,
    content_hash,
    tenant_id="tenant-a",
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
                        "tenant_id": tenant_id,
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


def test_replacement_archives_previous_active_chunks():
    suffix = uuid.uuid4().hex[:10]

    chunk_table = f"rag_snap_chunks_{suffix}"
    hash_table = f"rag_snap_hashes_{suffix}"
    document_table = f"rag_snap_docs_{suffix}"
    version_table = f"rag_snap_versions_{suffix}"
    snapshot_table = f"rag_snap_history_{suffix}"

    space = EmbeddingSpace(
        provider="openai",
        model="snapshot-model",
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

    replacement = (
        PostgresDocumentReplacementRepository(
            database_url=DATABASE_URL,
            chunk_table_name=chunk_table,
            hash_table_name=hash_table,
            document_table_name=document_table,
            version_table_name=version_table,
            version_chunk_table_name=snapshot_table,
            embedding_space=space,
        )
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
                content="historical version one",
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

        filters = RetrievalFilters(
            metadata={
                "tenant_id": "tenant-a"
            }
        )

        replacement.replace(
            prepared(
                document_id="doc-1",
                content="active version two",
                content_hash="b" * 64,
            ),
            filters=filters,
        )

        history = versions.list_versions(
            document_id="doc-1",
            tenant_id="tenant-a",
        )

        assert [
            item.version_number
            for item in history
        ] == [1, 2]

        v1_chunks = versions.list_version_chunks(
            document_id="doc-1",
            tenant_id="tenant-a",
            version_id=history[0].version_id,
        )

        assert len(v1_chunks) == 1
        assert (
            v1_chunks[0].content
            == "historical version one"
        )
        assert (
            v1_chunks[0].chunk_id
            == "old-chunk"
        )
        assert (
            v1_chunks[0].embedding
            == (1.0, 0.0, 0.0)
        )
        assert (
            v1_chunks[0].embedding_provider
            == "openai"
        )
        assert (
            v1_chunks[0].embedding_model
            == "snapshot-model"
        )
        assert (
            v1_chunks[0].embedding_dimensions
            == 3
        )

        # Current version is not archived until it is replaced.
        v2_chunks_before = (
            versions.list_version_chunks(
                document_id="doc-1",
                tenant_id="tenant-a",
                version_id=history[1].version_id,
            )
        )

        assert v2_chunks_before == []

        replacement.replace(
            prepared(
                document_id="doc-1",
                content="active version three",
                content_hash="c" * 64,
            ),
            filters=filters,
        )

        history = versions.list_versions(
            document_id="doc-1",
            tenant_id="tenant-a",
        )

        assert [
            item.version_number
            for item in history
        ] == [1, 2, 3]

        v2_chunks_after = (
            versions.list_version_chunks(
                document_id="doc-1",
                tenant_id="tenant-a",
                version_id=history[1].version_id,
            )
        )

        assert len(v2_chunks_after) == 1
        assert (
            v2_chunks_after[0].content
            == "active version two"
        )

        # Tenant isolation also applies to snapshot reads.
        hidden = versions.list_version_chunks(
            document_id="doc-1",
            tenant_id="tenant-b",
            version_id=history[0].version_id,
        )

        assert hidden == []

    finally:
        store.drop_schema()
        hashes.drop_schema()
        versions.drop_schema()
