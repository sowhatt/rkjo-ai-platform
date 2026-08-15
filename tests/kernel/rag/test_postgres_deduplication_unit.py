import pytest

from rkjo_kernel.rag.postgres_deduplication import (
    PostgresDocumentHashRegistry,
)


def test_registry_requires_database_url():
    with pytest.raises(
        ValueError,
        match="database_url",
    ):
        PostgresDocumentHashRegistry(
            database_url=" ",
        )


def test_registry_requires_table_name():
    with pytest.raises(
        ValueError,
        match="table_name",
    ):
        PostgresDocumentHashRegistry(
            database_url=(
                "postgresql://example"
            ),
            table_name=" ",
        )


def test_registry_rejects_empty_hash():
    registry = (
        PostgresDocumentHashRegistry(
            database_url=(
                "postgresql://example"
            )
        )
    )

    with pytest.raises(
        ValueError,
        match="content_hash",
    ):
        registry._validate_hash(
            " "
        )
