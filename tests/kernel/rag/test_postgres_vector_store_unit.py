import pytest

from rkjo_kernel.rag.postgres_vector_store import (
    PostgresPgVectorStore,
)


def test_store_requires_database_url():
    with pytest.raises(
        ValueError,
        match="database_url",
    ):
        PostgresPgVectorStore(
            database_url=" ",
            dimensions=16,
        )


def test_store_requires_positive_dimensions():
    with pytest.raises(
        ValueError,
        match="dimensions",
    ):
        PostgresPgVectorStore(
            database_url=(
                "postgresql://example"
            ),
            dimensions=0,
        )


def test_embedding_dimension_is_validated():
    store = PostgresPgVectorStore(
        database_url=(
            "postgresql://example"
        ),
        dimensions=3,
    )

    with pytest.raises(
        ValueError,
        match="dimensions",
    ):
        store._validate_embedding(
            [1.0, 2.0]
        )
