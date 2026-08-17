import os
import uuid

from rkjo_kernel.rag.embedding_space import (
    EmbeddingSpace,
)
from rkjo_kernel.rag.models import (
    DocumentChunk,
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


def test_delete_is_scoped_by_tenant():
    table_name = (
        "rag_delete_test_"
        + uuid.uuid4().hex[:12]
    )

    store = PostgresPgVectorStore(
        database_url=DATABASE_URL,
        dimensions=3,
        table_name=table_name,
        embedding_space=EmbeddingSpace(
            provider="openai",
            model="test-model",
            dimensions=3,
        ),
    )

    try:
        store.initialize_schema()

        store.add(
            chunk=DocumentChunk(
                document_id="doc-a",
                chunk_id="doc-a-1",
                content="Tenant A",
                chunk_index=0,
                metadata={
                    "tenant_id": "tenant-a"
                },
            ),
            embedding=[
                1.0,
                0.0,
                0.0,
            ],
        )

        # Wrong tenant must delete nothing.
        deleted = store.delete_document(
            "doc-a",
            filters=RetrievalFilters(
                metadata={
                    "tenant_id": "tenant-b"
                }
            ),
        )

        assert deleted == 0
        assert store.count() == 1

        # Correct tenant deletes the row.
        deleted = store.delete_document(
            "doc-a",
            filters=RetrievalFilters(
                metadata={
                    "tenant_id": "tenant-a"
                }
            ),
        )

        assert deleted == 1
        assert store.count() == 0

    finally:
        store.drop_schema()
