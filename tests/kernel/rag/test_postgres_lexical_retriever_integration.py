import os
import uuid

from rkjo_kernel.rag.embedding_space import (
    EmbeddingSpace,
)
from rkjo_kernel.rag.models import (
    DocumentChunk,
)
from rkjo_kernel.rag.postgres_lexical_retriever import (
    PostgresLexicalRetriever,
)
from rkjo_kernel.rag.postgres_vector_store import (
    PostgresPgVectorStore,
)


DATABASE_URL = os.getenv(
    "RKJO_TEST_DATABASE_URL",
    "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
)


def test_postgres_lexical_search_finds_exact_reference():
    table_name = (
        "rag_lexical_test_"
        + uuid.uuid4().hex[:12]
    )

    space = EmbeddingSpace(
        provider="openai",
        model="test-model",
        dimensions=3,
    )

    store = PostgresPgVectorStore(
        database_url=DATABASE_URL,
        dimensions=3,
        table_name=table_name,
        embedding_space=space,
    )

    lexical = PostgresLexicalRetriever(
        database_url=DATABASE_URL,
        table_name=table_name,
        embedding_space=space,
    )

    try:
        store.initialize_schema()
        lexical.initialize_schema()

        store.add(
            chunk=DocumentChunk(
                document_id="exact-doc",
                chunk_id="exact-chunk",
                content=(
                    "Référence AGRIREF2026. "
                    "Dossier technique du maïs."
                ),
                chunk_index=0,
            ),
            embedding=[
                1.0,
                0.0,
                0.0,
            ],
        )

        store.add(
            chunk=DocumentChunk(
                document_id="generic-doc",
                chunk_id="generic-chunk",
                content=(
                    "Informations agricoles "
                    "générales."
                ),
                chunk_index=0,
            ),
            embedding=[
                0.0,
                1.0,
                0.0,
            ],
        )

        results = lexical.retrieve(
            "AGRIREF2026",
            limit=5,
        )

        assert len(results) == 1

        assert (
            results[0].chunk.document_id
            == "exact-doc"
        )

        assert results[0].score > 0

    finally:
        store.drop_schema()
