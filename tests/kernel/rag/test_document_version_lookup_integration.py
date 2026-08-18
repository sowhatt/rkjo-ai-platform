import os
import uuid

import psycopg

from rkjo_kernel.rag.postgres_document_versioning import (
    PostgresDocumentVersionRepository,
)


DATABASE_URL = os.getenv(
    "RKJO_TEST_DATABASE_URL",
    "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
)


def test_exact_version_lookup_is_tenant_scoped():
    suffix = uuid.uuid4().hex[:10]

    document_table = (
        f"rag_lookup_docs_{suffix}"
    )
    version_table = (
        f"rag_lookup_versions_{suffix}"
    )

    repository = (
        PostgresDocumentVersionRepository(
            database_url=DATABASE_URL,
            document_table_name=document_table,
            version_table_name=version_table,
        )
    )

    repository.initialize_schema()

    try:
        version_id = str(uuid.uuid4())

        with psycopg.connect(
            DATABASE_URL
        ) as connection:
            connection.execute(
                f"""
                INSERT INTO {document_table} (
                    document_id,
                    tenant_id,
                    current_version
                )
                VALUES (%s, %s, %s)
                """,
                (
                    "doc-1",
                    "tenant-a",
                    2,
                ),
            )

            connection.execute(
                f"""
                INSERT INTO {version_table} (
                    version_id,
                    document_id,
                    tenant_id,
                    version_number,
                    content_hash
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    version_id,
                    "doc-1",
                    "tenant-a",
                    2,
                    "b" * 64,
                ),
            )

            connection.commit()

        found = repository.get_version(
            document_id="doc-1",
            tenant_id="tenant-a",
            version_number=2,
        )

        assert found is not None
        assert found.version_id == version_id
        assert found.version_number == 2

        hidden = repository.get_version(
            document_id="doc-1",
            tenant_id="tenant-b",
            version_number=2,
        )

        assert hidden is None

    finally:
        repository.drop_schema()
