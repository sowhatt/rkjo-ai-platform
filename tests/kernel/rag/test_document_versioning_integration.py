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
    tenant_id,
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


def test_replacements_increment_document_versions():
    suffix = uuid.uuid4().hex[:10]

    chunk_table = f"rag_v_chunks_{suffix}"
    hash_table = f"rag_v_hashes_{suffix}"
    document_table = f"rag_v_docs_{suffix}"
    version_table = f"rag_v_versions_{suffix}"

    space = EmbeddingSpace(
        provider="openai",
        model="test",
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

    replacement = (
        PostgresDocumentReplacementRepository(
            database_url=DATABASE_URL,
            chunk_table_name=chunk_table,
            hash_table_name=hash_table,
            document_table_name=document_table,
            version_table_name=version_table,
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
                chunk_id="old",
                content="version one",
                chunk_index=0,
                metadata={
                    "tenant_id": "tenant-a",
                    "content_hash": old_hash,
                },
            ),
            embedding=[1.0, 0.0, 0.0],
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

        result = replacement.replace(
            prepared(
                document_id="doc-1",
                content="version two",
                content_hash="b" * 64,
                tenant_id="tenant-a",
            ),
            filters=filters,
        )

        assert result is not None

        state = versions.get_document_state(
            document_id="doc-1",
            tenant_id="tenant-a",
        )

        assert state.current_version == 2

        history = versions.list_versions(
            document_id="doc-1",
            tenant_id="tenant-a",
        )

        assert [
            item.version_number
            for item in history
        ] == [1, 2]

        assert history[0].content_hash == old_hash
        assert history[1].content_hash == "b" * 64

        replacement.replace(
            prepared(
                document_id="doc-1",
                content="version three",
                content_hash="c" * 64,
                tenant_id="tenant-a",
            ),
            filters=filters,
        )

        state = versions.get_document_state(
            document_id="doc-1",
            tenant_id="tenant-a",
        )

        assert state.current_version == 3

        history = versions.list_versions(
            document_id="doc-1",
            tenant_id="tenant-a",
        )

        assert [
            item.version_number
            for item in history
        ] == [1, 2, 3]

    finally:
        store.drop_schema()
        hashes.drop_schema()
        versions.drop_schema()


def test_version_registry_is_tenant_isolated():
    suffix = uuid.uuid4().hex[:10]

    versions = PostgresDocumentVersionRepository(
        database_url=DATABASE_URL,
        document_table_name=f"rag_iso_docs_{suffix}",
        version_table_name=f"rag_iso_versions_{suffix}",
    )

    versions.initialize_schema()

    try:
        assert (
            versions.get_document_state(
                document_id="doc-x",
                tenant_id="tenant-a",
            )
            is None
        )

        assert (
            versions.list_versions(
                document_id="doc-x",
                tenant_id="tenant-b",
            )
            == []
        )

    finally:
        versions.drop_schema()
