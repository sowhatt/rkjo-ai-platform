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
from rkjo_kernel.rag.retrieval_filters import (
    RetrievalFilters,
)


DATABASE_URL = os.getenv(
    "RKJO_TEST_DATABASE_URL",
    "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
)


def test_lexical_filters_metadata_before_ranking():
    table_name = (
        "rag_lex_meta_"
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
                document_id="health-doc",
                chunk_id="health-chunk",
                content=(
                    "Référence commune AGRI2026"
                ),
                chunk_index=0,
                metadata={
                    "country": "benin",
                    "domain": "sante",
                },
            ),
            embedding=[
                1.0,
                0.0,
                0.0,
            ],
        )

        store.add(
            chunk=DocumentChunk(
                document_id="agri-doc",
                chunk_id="agri-chunk",
                content=(
                    "Référence commune AGRI2026"
                ),
                chunk_index=0,
                metadata={
                    "country": "benin",
                    "domain": "agriculture",
                },
            ),
            embedding=[
                0.0,
                1.0,
                0.0,
            ],
        )

        results = lexical.retrieve(
            "AGRI2026",
            limit=5,
            filters=RetrievalFilters(
                metadata={
                    "domain": "agriculture",
                }
            ),
        )

        assert len(results) == 1
        assert (
            results[0].chunk.document_id
            == "agri-doc"
        )

    finally:
        store.drop_schema()
