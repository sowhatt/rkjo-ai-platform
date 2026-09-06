"""PostgreSQL repository for the AssurGov Santé data catalog."""

from __future__ import annotations

import json

import psycopg
from psycopg.types.json import Jsonb

from rkjo_assurgov_sante.catalog.models import DataSource


class PostgresDataSourceRepository:
    def __init__(
        self,
        database_url: str,
    ) -> None:
        if not database_url.strip():
            raise ValueError(
                "database_url must not be empty."
            )

        self.database_url = database_url
        self._ensure_schema()

    def _connect(self):
        return psycopg.connect(
            self.database_url
        )

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                assurgov_data_sources (
                    tenant_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    description TEXT,
                    is_read_only BOOLEAN NOT NULL
                        DEFAULT TRUE,
                    environment TEXT NOT NULL
                        DEFAULT 'production',
                    connection_metadata JSONB NOT NULL
                        DEFAULT '{}'::jsonb,
                    connection_status TEXT NOT NULL
                        DEFAULT 'unknown',
                    last_scan_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL
                        DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL
                        DEFAULT NOW(),

                    PRIMARY KEY (
                        tenant_id,
                        source_id
                    ),

                    UNIQUE (
                        tenant_id,
                        name
                    )
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                assurgov_data_assets (
                    tenant_id TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    data_source_id TEXT NOT NULL,
                    schema_name TEXT NOT NULL,
                    asset_name TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    domain TEXT,
                    owner TEXT,
                    criticality TEXT,
                    description TEXT,
                    created_at TIMESTAMPTZ NOT NULL
                        DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL
                        DEFAULT NOW(),

                    PRIMARY KEY (
                        tenant_id,
                        asset_id
                    ),

                    FOREIGN KEY (
                        tenant_id,
                        data_source_id
                    )
                    REFERENCES assurgov_data_sources (
                        tenant_id,
                        source_id
                    )
                    ON DELETE CASCADE,

                    UNIQUE (
                        tenant_id,
                        data_source_id,
                        schema_name,
                        asset_name
                    )
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                assurgov_data_fields (
                    tenant_id TEXT NOT NULL,
                    field_id TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    field_name TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    ordinal_position INTEGER NOT NULL,
                    is_nullable BOOLEAN NOT NULL
                        DEFAULT TRUE,
                    is_sensitive BOOLEAN NOT NULL
                        DEFAULT FALSE,
                    business_term TEXT,
                    description TEXT,
                    created_at TIMESTAMPTZ NOT NULL
                        DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL
                        DEFAULT NOW(),

                    PRIMARY KEY (
                        tenant_id,
                        field_id
                    ),

                    FOREIGN KEY (
                        tenant_id,
                        asset_id
                    )
                    REFERENCES assurgov_data_assets (
                        tenant_id,
                        asset_id
                    )
                    ON DELETE CASCADE,

                    UNIQUE (
                        tenant_id,
                        asset_id,
                        field_name
                    ),

                    CHECK (
                        ordinal_position >= 1
                    )
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                assurgov_data_source_scans (
                    tenant_id TEXT NOT NULL,
                    scan_id TEXT NOT NULL,
                    data_source_id TEXT NOT NULL,
                    scan_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    assets_found INTEGER NOT NULL
                        DEFAULT 0,
                    fields_found INTEGER NOT NULL
                        DEFAULT 0,
                    message TEXT,
                    source_snapshot JSONB NOT NULL
                        DEFAULT '{}'::jsonb,
                    started_at TIMESTAMPTZ,
                    finished_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL
                        DEFAULT NOW(),

                    PRIMARY KEY (
                        tenant_id,
                        scan_id
                    ),

                    FOREIGN KEY (
                        tenant_id,
                        data_source_id
                    )
                    REFERENCES assurgov_data_sources (
                        tenant_id,
                        source_id
                    )
                    ON DELETE CASCADE,

                    CHECK (
                        assets_found >= 0
                    ),

                    CHECK (
                        fields_found >= 0
                    ),

                    CHECK (
                        finished_at IS NULL
                        OR started_at IS NULL
                        OR finished_at >= started_at
                    )
                )
                """
            )

    def save(
        self,
        source: DataSource,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO assurgov_data_sources (
                    tenant_id,
                    source_id,
                    name,
                    source_type,
                    description,
                    is_read_only,
                    environment,
                    connection_metadata,
                    connection_status,
                    last_scan_at
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                ON CONFLICT (
                    tenant_id,
                    source_id
                )
                DO UPDATE SET
                    name = EXCLUDED.name,
                    source_type = EXCLUDED.source_type,
                    description = EXCLUDED.description,
                    is_read_only =
                        EXCLUDED.is_read_only,
                    environment =
                        EXCLUDED.environment,
                    connection_metadata =
                        EXCLUDED.connection_metadata,
                    connection_status =
                        EXCLUDED.connection_status,
                    last_scan_at =
                        EXCLUDED.last_scan_at,
                    updated_at = NOW()
                """,
                (
                    source.tenant_id,
                    source.source_id,
                    source.name,
                    source.source_type,
                    source.description,
                    source.is_read_only,
                    source.environment,
                    Jsonb(
                        source.connection_metadata
                    ),
                    source.connection_status,
                    source.last_scan_at,
                ),
            )

    def get(
        self,
        *,
        tenant_id: str,
        source_id: str,
    ) -> DataSource | None:
        tenant_id = tenant_id.strip()
        source_id = source_id.strip()

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    name,
                    source_type,
                    description,
                    is_read_only,
                    environment,
                    connection_metadata,
                    connection_status,
                    last_scan_at
                FROM assurgov_data_sources
                WHERE tenant_id = %s
                  AND source_id = %s
                """,
                (
                    tenant_id,
                    source_id,
                ),
            ).fetchone()

        if row is None:
            return None

        metadata = row[5]

        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        return DataSource(
            source_id=source_id,
            tenant_id=tenant_id,
            name=row[0],
            source_type=row[1],
            description=row[2],
            is_read_only=row[3],
            environment=row[4],
            connection_metadata=dict(metadata),
            connection_status=row[6],
            last_scan_at=row[7],
        )

    def get_by_name(
        self,
        *,
        tenant_id: str,
        name: str,
    ) -> DataSource | None:
        tenant_id = tenant_id.strip()
        name = name.strip()

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT source_id
                FROM assurgov_data_sources
                WHERE tenant_id = %s
                  AND name = %s
                """,
                (
                    tenant_id,
                    name,
                ),
            ).fetchone()

        if row is None:
            return None

        return self.get(
            tenant_id=tenant_id,
            source_id=row[0],
        )

    def list_for_tenant(
        self,
        tenant_id: str,
    ) -> list[DataSource]:
        tenant_id = tenant_id.strip()

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT source_id
                FROM assurgov_data_sources
                WHERE tenant_id = %s
                ORDER BY name, source_id
                """,
                (tenant_id,),
            ).fetchall()

        return [
            self.get(
                tenant_id=tenant_id,
                source_id=row[0],
            )
            for row in rows
        ]
