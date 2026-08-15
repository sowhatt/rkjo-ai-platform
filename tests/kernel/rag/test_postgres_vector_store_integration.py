import os
from uuid import uuid4

import psycopg
import pytest

from rkjo_kernel.rag.chunking import TextChunker
from rkjo_kernel.rag.embedding import (
    DeterministicEmbeddingProvider,
)
from rkjo_kernel.rag.models import (
    Document,
    DocumentChunk,
)
from rkjo_kernel.rag.postgres_vector_store import (
    PostgresPgVectorStore,
)
from rkjo_kernel.rag.retriever import Retriever


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
    reason=(
        "PostgreSQL integration database "
        "is not available."
    ),
)


@pytest.fixture
def store():
    table_name = (
        "rag_chunks_test_"
        + uuid4().hex
    )

    vector_store = (
        PostgresPgVectorStore(
            database_url=DATABASE_URL,
            dimensions=16,
            table_name=table_name,
        )
    )

    vector_store.initialize_schema()

    yield vector_store

    vector_store.drop_schema()


def test_pgvector_extension_is_enabled(
    store,
):
    with psycopg.connect(
        DATABASE_URL
    ) as connection:
        row = connection.execute(
            """
            SELECT extname
            FROM pg_extension
            WHERE extname = 'vector'
            """
        ).fetchone()

    assert row is not None
    assert row[0] == "vector"


def test_add_and_search_chunk(
    store,
):
    provider = (
        DeterministicEmbeddingProvider(
            dimensions=16
        )
    )

    climate = DocumentChunk(
        document_id="climate",
        chunk_id="climate-001",
        content=(
            "rain drought climate"
        ),
        chunk_index=0,
        metadata={
            "source": "adip"
        },
    )

    insurance = DocumentChunk(
        document_id="insurance",
        chunk_id="insurance-001",
        content=(
            "bank insurance contract"
        ),
        chunk_index=0,
    )

    store.add(
        chunk=climate,
        embedding=provider.embed(
            climate.content
        ),
    )

    store.add(
        chunk=insurance,
        embedding=provider.embed(
            insurance.content
        ),
    )

    results = store.search(
        query_embedding=provider.embed(
            "rain drought climate"
        ),
        limit=1,
    )

    assert len(results) == 1

    assert (
        results[0]
        .chunk
        .document_id
        == "climate"
    )

    assert results[0].chunk.metadata == {
        "source": "adip"
    }

    assert results[0].score > 0.99


def test_retriever_works_without_changes(
    store,
):
    retriever = Retriever(
        chunker=TextChunker(
            chunk_size=100,
            overlap=0,
        ),
        embedding_provider=(
            DeterministicEmbeddingProvider(
                dimensions=16
            )
        ),
        vector_store=store,
    )

    count = retriever.ingest(
        Document(
            document_id="agriculture",
            content=(
                "soil rainfall crop yield"
            ),
            metadata={
                "product": "ADIP"
            },
        )
    )

    assert count == 1

    results = retriever.retrieve(
        "soil rainfall crop yield",
        limit=1,
    )

    assert len(results) == 1

    assert (
        results[0]
        .chunk
        .document_id
        == "agriculture"
    )


def test_chunks_persist_across_store_instances(
    store,
):
    provider = (
        DeterministicEmbeddingProvider(
            dimensions=16
        )
    )

    chunk = DocumentChunk(
        document_id="persistent-doc",
        chunk_id="persistent-chunk",
        content="persistent knowledge",
        chunk_index=0,
    )

    store.add(
        chunk=chunk,
        embedding=provider.embed(
            chunk.content
        ),
    )

    second_store = (
        PostgresPgVectorStore(
            database_url=DATABASE_URL,
            dimensions=16,
            table_name=store.table_name,
        )
    )

    assert second_store.count() == 1

    results = second_store.search(
        query_embedding=provider.embed(
            "persistent knowledge"
        ),
        limit=1,
    )

    assert (
        results[0]
        .chunk
        .chunk_id
        == "persistent-chunk"
    )


def test_delete_document(
    store,
):
    provider = (
        DeterministicEmbeddingProvider(
            dimensions=16
        )
    )

    for index in range(2):
        chunk = DocumentChunk(
            document_id="delete-me",
            chunk_id=f"delete-{index}",
            content=f"knowledge {index}",
            chunk_index=index,
        )

        store.add(
            chunk=chunk,
            embedding=provider.embed(
                chunk.content
            ),
        )

    assert store.count() == 2

    deleted = store.delete_document(
        "delete-me"
    )

    assert deleted == 2
    assert store.count() == 0
