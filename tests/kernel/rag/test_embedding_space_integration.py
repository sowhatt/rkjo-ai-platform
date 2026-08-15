import os
import uuid

import pytest

from rkjo_kernel.rag.embedding_space import (
    EmbeddingSpace,
)
from rkjo_kernel.rag.models import DocumentChunk
from rkjo_kernel.rag.postgres_vector_store import (
    PostgresPgVectorStore,
)


DATABASE_URL = os.getenv(
    "RKJO_TEST_DATABASE_URL",
    "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
)


def make_store(
    table_name,
    *,
    provider,
    model,
):
    return PostgresPgVectorStore(
        database_url=DATABASE_URL,
        dimensions=3,
        table_name=table_name,
        embedding_space=EmbeddingSpace(
            provider=provider,
            model=model,
            dimensions=3,
        ),
    )


def test_search_isolates_embedding_spaces():
    table_name = (
        "rag_space_test_"
        + uuid.uuid4().hex[:12]
    )

    openai = make_store(
        table_name,
        provider="openai",
        model="model-a",
    )

    deterministic = make_store(
        table_name,
        provider="deterministic",
        model="deterministic-v1",
    )

    other_model = make_store(
        table_name,
        provider="openai",
        model="model-b",
    )

    try:
        openai.initialize_schema()

        openai.add(
            chunk=DocumentChunk(
                document_id="openai-doc",
                chunk_id="openai-chunk",
                content="OpenAI compatible chunk",
                chunk_index=0,
            ),
            embedding=[1.0, 0.0, 0.0],
        )

        deterministic.add(
            chunk=DocumentChunk(
                document_id="det-doc",
                chunk_id="det-chunk",
                content="Deterministic incompatible chunk",
                chunk_index=0,
            ),
            embedding=[1.0, 0.0, 0.0],
        )

        other_model.add(
            chunk=DocumentChunk(
                document_id="other-doc",
                chunk_id="other-chunk",
                content="Different OpenAI model",
                chunk_index=0,
            ),
            embedding=[1.0, 0.0, 0.0],
        )

        results = openai.search(
            query_embedding=[
                1.0,
                0.0,
                0.0,
            ],
            limit=10,
        )

        assert [
            item.chunk.document_id
            for item in results
        ] == ["openai-doc"]

    finally:
        openai.drop_schema()


def test_legacy_rows_are_not_returned_by_scoped_search():
    table_name = (
        "rag_legacy_test_"
        + uuid.uuid4().hex[:12]
    )

    legacy = PostgresPgVectorStore(
        database_url=DATABASE_URL,
        dimensions=3,
        table_name=table_name,
    )

    scoped = make_store(
        table_name,
        provider="openai",
        model="model-a",
    )

    try:
        legacy.initialize_schema()

        legacy.add(
            chunk=DocumentChunk(
                document_id="legacy-doc",
                chunk_id="legacy-chunk",
                content="Legacy vector",
                chunk_index=0,
            ),
            embedding=[1.0, 0.0, 0.0],
        )

        scoped.add(
            chunk=DocumentChunk(
                document_id="current-doc",
                chunk_id="current-chunk",
                content="Current vector",
                chunk_index=0,
            ),
            embedding=[1.0, 0.0, 0.0],
        )

        results = scoped.search(
            query_embedding=[
                1.0,
                0.0,
                0.0,
            ],
            limit=10,
        )

        assert [
            item.chunk.document_id
            for item in results
        ] == ["current-doc"]

    finally:
        legacy.drop_schema()
