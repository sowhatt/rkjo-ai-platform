"""Repository contracts for the AssurGov Santé catalog."""

from __future__ import annotations

from typing import Protocol

from rkjo_assurgov_sante.catalog.models import DataSource


class DataSourceRepository(Protocol):
    def save(self, source: DataSource) -> None:
        ...

    def get(
        self,
        *,
        tenant_id: str,
        source_id: str,
    ) -> DataSource | None:
        ...

    def get_by_name(
        self,
        *,
        tenant_id: str,
        name: str,
    ) -> DataSource | None:
        ...

    def list_for_tenant(
        self,
        tenant_id: str,
    ) -> list[DataSource]:
        ...
