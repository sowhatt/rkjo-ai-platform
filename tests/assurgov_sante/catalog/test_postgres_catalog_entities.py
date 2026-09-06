import os
import uuid
from datetime import UTC, datetime

import psycopg
import pytest

from rkjo_assurgov_sante.catalog.models import (
    DataAsset,
    DataField,
    DataSource,
    DataSourceScan,
)
from rkjo_assurgov_sante.catalog.postgres_repository import (
    PostgresDataAssetRepository,
    PostgresDataFieldRepository,
    PostgresDataSourceRepository,
    PostgresDataSourceScanRepository,
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


def create_source(database_url, *, tenant_id, suffix):
    source = DataSource(
        source_id=f"source-{suffix}",
        tenant_id=tenant_id,
        name=f"NOEMIE-{suffix}",
        source_type="sql_server",
    )

    PostgresDataSourceRepository(
        database_url
    ).save(source)

    return source


def test_asset_and_field_survive_repository_recreation(
    database_url,
):
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"tenant-{suffix}"

    source = create_source(
        database_url,
        tenant_id=tenant_id,
        suffix=suffix,
    )

    asset = DataAsset(
        asset_id=f"asset-{suffix}",
        tenant_id=tenant_id,
        data_source_id=source.source_id,
        schema_name="dbo",
        asset_name="prestations",
        asset_type="table",
        domain="sante",
    )

    asset_repository = PostgresDataAssetRepository(
        database_url
    )
    asset_repository.save(asset)

    field = DataField(
        field_id=f"field-{suffix}",
        tenant_id=tenant_id,
        asset_id=asset.asset_id,
        field_name="beneficiaire_id",
        data_type="varchar",
        ordinal_position=1,
        is_sensitive=True,
    )

    PostgresDataFieldRepository(
        database_url
    ).save(field)

    assert PostgresDataAssetRepository(
        database_url
    ).get(
        tenant_id=tenant_id,
        asset_id=asset.asset_id,
    ) == asset

    assert PostgresDataFieldRepository(
        database_url
    ).get(
        tenant_id=tenant_id,
        field_id=field.field_id,
    ) == field


def test_scan_survives_repository_recreation(
    database_url,
):
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"tenant-{suffix}"

    source = create_source(
        database_url,
        tenant_id=tenant_id,
        suffix=suffix,
    )

    now = datetime.now(UTC)

    scan = DataSourceScan(
        scan_id=f"scan-{suffix}",
        tenant_id=tenant_id,
        data_source_id=source.source_id,
        scan_type="metadata",
        status="completed",
        assets_found=12,
        fields_found=96,
        source_snapshot={
            "database": "sante",
        },
        started_at=now,
        finished_at=now,
    )

    repository = PostgresDataSourceScanRepository(
        database_url
    )
    repository.save(scan)

    loaded = PostgresDataSourceScanRepository(
        database_url
    ).get(
        tenant_id=tenant_id,
        scan_id=scan.scan_id,
    )

    assert loaded == scan


def test_cross_tenant_asset_reference_is_rejected(
    database_url,
):
    suffix = uuid.uuid4().hex[:8]

    source = create_source(
        database_url,
        tenant_id=f"tenant-a-{suffix}",
        suffix=suffix,
    )

    asset = DataAsset(
        asset_id=f"asset-{suffix}",
        tenant_id=f"tenant-b-{suffix}",
        data_source_id=source.source_id,
        schema_name="dbo",
        asset_name="prestations",
        asset_type="table",
    )

    with pytest.raises(
        psycopg.errors.ForeignKeyViolation
    ):
        PostgresDataAssetRepository(
            database_url
        ).save(asset)


def test_cross_tenant_field_reference_is_rejected(
    database_url,
):
    suffix = uuid.uuid4().hex[:8]
    tenant_a = f"tenant-a-{suffix}"

    source = create_source(
        database_url,
        tenant_id=tenant_a,
        suffix=suffix,
    )

    asset = DataAsset(
        asset_id=f"asset-{suffix}",
        tenant_id=tenant_a,
        data_source_id=source.source_id,
        schema_name="dbo",
        asset_name="prestations",
        asset_type="table",
    )

    PostgresDataAssetRepository(
        database_url
    ).save(asset)

    field = DataField(
        field_id=f"field-{suffix}",
        tenant_id=f"tenant-b-{suffix}",
        asset_id=asset.asset_id,
        field_name="beneficiaire_id",
        data_type="varchar",
        ordinal_position=1,
    )

    with pytest.raises(
        psycopg.errors.ForeignKeyViolation
    ):
        PostgresDataFieldRepository(
            database_url
        ).save(field)


def test_source_delete_cascades_catalog_children(
    database_url,
):
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"tenant-{suffix}"

    source = create_source(
        database_url,
        tenant_id=tenant_id,
        suffix=suffix,
    )

    asset = DataAsset(
        asset_id=f"asset-{suffix}",
        tenant_id=tenant_id,
        data_source_id=source.source_id,
        schema_name="dbo",
        asset_name="prestations",
        asset_type="table",
    )

    PostgresDataAssetRepository(
        database_url
    ).save(asset)

    field = DataField(
        field_id=f"field-{suffix}",
        tenant_id=tenant_id,
        asset_id=asset.asset_id,
        field_name="beneficiaire_id",
        data_type="varchar",
        ordinal_position=1,
    )

    PostgresDataFieldRepository(
        database_url
    ).save(field)

    scan = DataSourceScan(
        scan_id=f"scan-{suffix}",
        tenant_id=tenant_id,
        data_source_id=source.source_id,
        scan_type="metadata",
        status="completed",
    )

    PostgresDataSourceScanRepository(
        database_url
    ).save(scan)

    with psycopg.connect(
        database_url
    ) as connection:
        connection.execute(
            """
            DELETE FROM assurgov_data_sources
            WHERE tenant_id = %s
              AND source_id = %s
            """,
            (
                tenant_id,
                source.source_id,
            ),
        )

    assert PostgresDataAssetRepository(
        database_url
    ).get(
        tenant_id=tenant_id,
        asset_id=asset.asset_id,
    ) is None

    assert PostgresDataFieldRepository(
        database_url
    ).get(
        tenant_id=tenant_id,
        field_id=field.field_id,
    ) is None

    assert PostgresDataSourceScanRepository(
        database_url
    ).get(
        tenant_id=tenant_id,
        scan_id=scan.scan_id,
    ) is None


def test_lists_are_tenant_scoped(
    database_url,
):
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"tenant-{suffix}"

    source = create_source(
        database_url,
        tenant_id=tenant_id,
        suffix=suffix,
    )

    asset_repository = PostgresDataAssetRepository(
        database_url
    )

    asset = DataAsset(
        asset_id=f"asset-{suffix}",
        tenant_id=tenant_id,
        data_source_id=source.source_id,
        schema_name="dbo",
        asset_name="prestations",
        asset_type="table",
    )

    asset_repository.save(asset)

    assert asset_repository.list_for_source(
        tenant_id=tenant_id,
        data_source_id=source.source_id,
    ) == [asset]

    assert asset_repository.list_for_source(
        tenant_id=f"other-{suffix}",
        data_source_id=source.source_id,
    ) == []
