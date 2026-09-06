"""AssurGov Santé data catalog domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def _required(value: str, *, field_name: str) -> str:
    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{field_name} must not be empty."
        )

    return normalized


def _optional(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip()

    return normalized or None


@dataclass(frozen=True, slots=True)
class DataSource:
    source_id: str
    tenant_id: str
    name: str
    source_type: str
    description: str | None = None
    is_read_only: bool = True
    environment: str = "production"
    connection_metadata: dict[str, Any] = field(
        default_factory=dict
    )
    connection_status: str = "unknown"
    last_scan_at: datetime | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "source_id",
            "tenant_id",
            "name",
            "source_type",
            "environment",
            "connection_status",
        ):
            object.__setattr__(
                self,
                field_name,
                _required(
                    getattr(self, field_name),
                    field_name=field_name,
                ),
            )

        object.__setattr__(
            self,
            "description",
            _optional(self.description),
        )

        object.__setattr__(
            self,
            "connection_metadata",
            dict(self.connection_metadata),
        )


@dataclass(frozen=True, slots=True)
class DataAsset:
    asset_id: str
    tenant_id: str
    data_source_id: str
    schema_name: str
    asset_name: str
    asset_type: str
    domain: str | None = None
    owner: str | None = None
    criticality: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "asset_id",
            "tenant_id",
            "data_source_id",
            "schema_name",
            "asset_name",
            "asset_type",
        ):
            object.__setattr__(
                self,
                field_name,
                _required(
                    getattr(self, field_name),
                    field_name=field_name,
                ),
            )

        for field_name in (
            "domain",
            "owner",
            "criticality",
            "description",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional(
                    getattr(self, field_name)
                ),
            )


@dataclass(frozen=True, slots=True)
class DataField:
    field_id: str
    tenant_id: str
    asset_id: str
    field_name: str
    data_type: str
    ordinal_position: int
    is_nullable: bool = True
    is_sensitive: bool = False
    business_term: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "field_id",
            "tenant_id",
            "asset_id",
            "field_name",
            "data_type",
        ):
            object.__setattr__(
                self,
                field_name,
                _required(
                    getattr(self, field_name),
                    field_name=field_name,
                ),
            )

        if self.ordinal_position < 1:
            raise ValueError(
                "ordinal_position must be >= 1."
            )

        object.__setattr__(
            self,
            "business_term",
            _optional(self.business_term),
        )

        object.__setattr__(
            self,
            "description",
            _optional(self.description),
        )


@dataclass(frozen=True, slots=True)
class DataSourceScan:
    scan_id: str
    tenant_id: str
    data_source_id: str
    scan_type: str
    status: str
    assets_found: int = 0
    fields_found: int = 0
    message: str | None = None
    source_snapshot: dict[str, Any] = field(
        default_factory=dict
    )
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "scan_id",
            "tenant_id",
            "data_source_id",
            "scan_type",
            "status",
        ):
            object.__setattr__(
                self,
                field_name,
                _required(
                    getattr(self, field_name),
                    field_name=field_name,
                ),
            )

        if self.assets_found < 0:
            raise ValueError(
                "assets_found must be >= 0."
            )

        if self.fields_found < 0:
            raise ValueError(
                "fields_found must be >= 0."
            )

        if (
            self.started_at is not None
            and self.finished_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError(
                "finished_at must not be before started_at."
            )

        object.__setattr__(
            self,
            "message",
            _optional(self.message),
        )

        object.__setattr__(
            self,
            "source_snapshot",
            dict(self.source_snapshot),
        )
