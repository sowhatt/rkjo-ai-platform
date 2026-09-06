"""Application services for the AssurGov Santé data catalog."""

from __future__ import annotations

from rkjo_assurgov_sante.catalog.models import DataSource
from rkjo_assurgov_sante.catalog.repository import DataSourceRepository


def _required(value: str, *, field_name: str) -> str:
    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{field_name} must not be empty."
        )

    return normalized


class DataCatalogService:
    def __init__(
        self,
        repository: DataSourceRepository,
    ) -> None:
        self.repository = repository

    def create_source(
        self,
        source: DataSource,
    ) -> DataSource:
        existing_by_id = self.repository.get(
            tenant_id=source.tenant_id,
            source_id=source.source_id,
        )

        if existing_by_id is not None:
            raise ValueError(
                "Data source already exists."
            )

        existing_by_name = self.repository.get_by_name(
            tenant_id=source.tenant_id,
            name=source.name,
        )

        if existing_by_name is not None:
            raise ValueError(
                "A data source with the same name "
                "already exists for this tenant."
            )

        self.repository.save(source)

        return source

    def get_source(
        self,
        *,
        tenant_id: str,
        source_id: str,
    ) -> DataSource:
        tenant_id = _required(
            tenant_id,
            field_name="tenant_id",
        )

        source_id = _required(
            source_id,
            field_name="source_id",
        )

        source = self.repository.get(
            tenant_id=tenant_id,
            source_id=source_id,
        )

        if source is None:
            raise LookupError(
                "Data source not found."
            )

        return source

    def list_sources(
        self,
        *,
        tenant_id: str,
    ) -> list[DataSource]:
        tenant_id = _required(
            tenant_id,
            field_name="tenant_id",
        )

        return self.repository.list_for_tenant(
            tenant_id
        )
