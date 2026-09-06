import os
import uuid

import psycopg
import pytest

from rkjo_assurgov_sante.catalog.models import DataSource
from rkjo_assurgov_sante.catalog.postgres_repository import (
    PostgresDataSourceRepository,
)


DATABASE_URL = os.getenv(
    "RKJO_DATABASE_URL",
    "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
)


@pytest.fixture()
def database_url():
    try:
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute("SELECT 1")
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL is unavailable.")

    return DATABASE_URL


def make_source(
    *,
    suffix: str,
    tenant_id: str,
    source_id: str | None = None,
    name: str | None = None,
):
    return DataSource(
        source_id=source_id or f"source-{suffix}",
        tenant_id=tenant_id,
        name=name or f"NOEMIE-{suffix}",
        source_type="sql_server",
        description="Base prestations santé",
        connection_metadata={
            "database": "sante",
            "schema": "dbo",
        },
        connection_status="connected",
    )


def test_source_survives_repository_recreation(
    database_url,
):
    suffix = uuid.uuid4().hex[:8]

    source = make_source(
        suffix=suffix,
        tenant_id=f"tenant-{suffix}",
    )

    repository = PostgresDataSourceRepository(
        database_url
    )
    repository.save(source)

    recreated = PostgresDataSourceRepository(
        database_url
    )

    loaded = recreated.get(
        tenant_id=source.tenant_id,
        source_id=source.source_id,
    )

    assert loaded == source


def test_source_read_is_tenant_safe(
    database_url,
):
    suffix = uuid.uuid4().hex[:8]

    repository = PostgresDataSourceRepository(
        database_url
    )

    source = make_source(
        suffix=suffix,
        tenant_id=f"tenant-a-{suffix}",
    )

    repository.save(source)

    assert (
        repository.get(
            tenant_id=f"tenant-b-{suffix}",
            source_id=source.source_id,
        )
        is None
    )


def test_same_source_id_is_allowed_between_tenants(
    database_url,
):
    suffix = uuid.uuid4().hex[:8]
    source_id = f"shared-{suffix}"

    repository = PostgresDataSourceRepository(
        database_url
    )

    source_a = make_source(
        suffix=f"a-{suffix}",
        tenant_id=f"tenant-a-{suffix}",
        source_id=source_id,
    )

    source_b = make_source(
        suffix=f"b-{suffix}",
        tenant_id=f"tenant-b-{suffix}",
        source_id=source_id,
    )

    repository.save(source_a)
    repository.save(source_b)

    assert repository.get(
        tenant_id=source_a.tenant_id,
        source_id=source_id,
    ) == source_a

    assert repository.get(
        tenant_id=source_b.tenant_id,
        source_id=source_id,
    ) == source_b


def test_same_name_is_allowed_between_tenants(
    database_url,
):
    suffix = uuid.uuid4().hex[:8]
    shared_name = f"NOEMIE-{suffix}"

    repository = PostgresDataSourceRepository(
        database_url
    )

    source_a = make_source(
        suffix=f"a-{suffix}",
        tenant_id=f"tenant-a-{suffix}",
        name=shared_name,
    )

    source_b = make_source(
        suffix=f"b-{suffix}",
        tenant_id=f"tenant-b-{suffix}",
        name=shared_name,
    )

    repository.save(source_a)
    repository.save(source_b)

    assert repository.get_by_name(
        tenant_id=source_a.tenant_id,
        name=shared_name,
    ) == source_a

    assert repository.get_by_name(
        tenant_id=source_b.tenant_id,
        name=shared_name,
    ) == source_b


def test_list_for_tenant_is_isolated(
    database_url,
):
    suffix = uuid.uuid4().hex[:8]

    tenant_a = f"tenant-a-{suffix}"
    tenant_b = f"tenant-b-{suffix}"

    repository = PostgresDataSourceRepository(
        database_url
    )

    source_a1 = make_source(
        suffix=f"a1-{suffix}",
        tenant_id=tenant_a,
    )

    source_a2 = make_source(
        suffix=f"a2-{suffix}",
        tenant_id=tenant_a,
    )

    source_b = make_source(
        suffix=f"b-{suffix}",
        tenant_id=tenant_b,
    )

    repository.save(source_a1)
    repository.save(source_a2)
    repository.save(source_b)

    sources = repository.list_for_tenant(
        tenant_a
    )

    assert {
        source.source_id
        for source in sources
    } == {
        source_a1.source_id,
        source_a2.source_id,
    }
