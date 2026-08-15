import os
from uuid import uuid4

import psycopg
import pytest

from rkjo_kernel.rag.chunking import (
    TextChunker,
)
from rkjo_kernel.rag.embedding import (
    DeterministicEmbeddingProvider,
)
from rkjo_kernel.rag.hashing import (
    compute_content_hash,
)
from rkjo_kernel.rag.ingestion import (
    DocumentIngestionPipeline,
)
from rkjo_kernel.rag.loaders import (
    CompositeDocumentLoader,
)
from rkjo_kernel.rag.postgres_deduplication import (
    PostgresDocumentHashRegistry,
)
from rkjo_kernel.rag.postgres_vector_store import (
    PostgresPgVectorStore,
)
from rkjo_kernel.rag.retriever import (
    Retriever,
)


DATABASE_URL = os.getenv(
    "RKJO_TEST_DATABASE_URL",
    (
        "postgresql://rkjo:rkjo_password"
        "@localhost:5432/rkjo"
    ),
)


def database_available() -> bool:
    try:
        with psycopg.connect(
            DATABASE_URL,
            connect_timeout=2,
        ):
            return True
    except psycopg.Error:
        return False


pytestmark = pytest.mark.skipif(
    not database_available(),
    reason="PostgreSQL test database unavailable.",
)


@pytest.fixture
def registry():
    table_name = (
        "rag_hashes_test_"
        + uuid4().hex
    )

    instance = (
        PostgresDocumentHashRegistry(
            database_url=DATABASE_URL,
            table_name=table_name,
        )
    )

    instance.initialize_schema()

    yield instance

    instance.drop_schema()


def test_register_and_contains_hash(
    registry,
):
    content_hash = (
        compute_content_hash(
            "persistent document"
        )
    )

    assert not registry.contains(
        content_hash
    )

    registry.register(
        content_hash=content_hash,
        document_id="doc-001",
    )

    assert registry.contains(
        content_hash
    )

    assert (
        registry.get_document_id(
            content_hash
        )
        == "doc-001"
    )


def test_register_is_idempotent(
    registry,
):
    content_hash = (
        compute_content_hash(
            "same document"
        )
    )

    registry.register(
        content_hash=content_hash,
        document_id="doc-first",
    )

    registry.register(
        content_hash=content_hash,
        document_id="doc-second",
    )

    assert registry.count() == 1

    assert (
        registry.get_document_id(
            content_hash
        )
        == "doc-first"
    )


def test_hash_persists_across_instances(
    registry,
):
    content_hash = (
        compute_content_hash(
            "shared knowledge"
        )
    )

    registry.register(
        content_hash=content_hash,
        document_id="shared-doc",
    )

    second = (
        PostgresDocumentHashRegistry(
            database_url=DATABASE_URL,
            table_name=registry.table_name,
        )
    )

    assert second.contains(
        content_hash
    )

    assert (
        second.get_document_id(
            content_hash
        )
        == "shared-doc"
    )


def test_ingestion_deduplicates_after_registry_restart(
    registry,
    tmp_path,
):
    vector_table = (
        "rag_chunks_hash_test_"
        + uuid4().hex
    )

    vector_store = (
        PostgresPgVectorStore(
            database_url=DATABASE_URL,
            dimensions=16,
            table_name=vector_table,
        )
    )

    vector_store.initialize_schema()

    try:
        path = (
            tmp_path
            / "knowledge.txt"
        )

        path.write_text(
            (
                "soil climate rainfall "
                "crop yield"
            ),
            encoding="utf-8",
        )

        def make_pipeline(
            hash_registry,
        ):
            return (
                DocumentIngestionPipeline(
                    loader=(
                        CompositeDocumentLoader()
                    ),
                    retriever=Retriever(
                        chunker=TextChunker(
                            chunk_size=100,
                            overlap=0,
                        ),
                        embedding_provider=(
                            DeterministicEmbeddingProvider(
                                dimensions=16
                            )
                        ),
                        vector_store=(
                            vector_store
                        ),
                    ),
                    hash_registry=(
                        hash_registry
                    ),
                )
            )

        first = make_pipeline(
            registry
        ).ingest_file(
            path,
            document_id="doc-001",
        )

        second_registry = (
            PostgresDocumentHashRegistry(
                database_url=DATABASE_URL,
                table_name=registry.table_name,
            )
        )

        second = make_pipeline(
            second_registry
        ).ingest_file(
            path,
            document_id="doc-002",
        )

        assert first.duplicate is False
        assert second.duplicate is True
        assert second.chunk_count == 0

        assert vector_store.count() == 1

    finally:
        vector_store.drop_schema()
