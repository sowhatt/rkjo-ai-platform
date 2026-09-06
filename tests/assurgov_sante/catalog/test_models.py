from datetime import UTC, datetime, timedelta

import pytest

from rkjo_assurgov_sante.catalog.models import (
    DataAsset,
    DataField,
    DataSource,
    DataSourceScan,
)


def test_data_source_normalizes_required_values():
    source = DataSource(
        source_id=" src-1 ",
        tenant_id=" tenant-a ",
        name=" SQL Santé ",
        source_type=" sql_server ",
    )

    assert source.source_id == "src-1"
    assert source.tenant_id == "tenant-a"
    assert source.name == "SQL Santé"
    assert source.source_type == "sql_server"


def test_data_source_requires_tenant():
    with pytest.raises(ValueError, match="tenant_id"):
        DataSource(
            source_id="src-1",
            tenant_id=" ",
            name="NOEMIE",
            source_type="sql_server",
        )


def test_data_asset_is_tenant_scoped():
    asset = DataAsset(
        asset_id="asset-1",
        tenant_id="tenant-a",
        data_source_id="src-1",
        schema_name="dbo",
        asset_name="prestations",
        asset_type="table",
        domain="sante",
    )

    assert asset.tenant_id == "tenant-a"
    assert asset.asset_name == "prestations"
    assert asset.domain == "sante"


def test_data_field_rejects_invalid_ordinal_position():
    with pytest.raises(ValueError, match="ordinal_position"):
        DataField(
            field_id="field-1",
            tenant_id="tenant-a",
            asset_id="asset-1",
            field_name="beneficiaire_id",
            data_type="varchar",
            ordinal_position=0,
        )


def test_data_source_scan_rejects_negative_counts():
    with pytest.raises(ValueError, match="assets_found"):
        DataSourceScan(
            scan_id="scan-1",
            tenant_id="tenant-a",
            data_source_id="src-1",
            scan_type="metadata",
            status="completed",
            assets_found=-1,
        )


def test_data_source_scan_rejects_invalid_dates():
    started = datetime.now(UTC)

    with pytest.raises(ValueError, match="finished_at"):
        DataSourceScan(
            scan_id="scan-1",
            tenant_id="tenant-a",
            data_source_id="src-1",
            scan_type="metadata",
            status="completed",
            started_at=started,
            finished_at=started - timedelta(seconds=1),
        )
