import pytest

from rkjo_assurgov_sante.catalog.models import DataSource
from rkjo_assurgov_sante.catalog.service import DataCatalogService


class InMemoryDataSourceRepository:
    def __init__(self):
        self.sources = {}

    def save(self, source):
        self.sources[
            (source.tenant_id, source.source_id)
        ] = source

    def get(
        self,
        *,
        tenant_id,
        source_id,
    ):
        return self.sources.get(
            (tenant_id, source_id)
        )

    def get_by_name(
        self,
        *,
        tenant_id,
        name,
    ):
        for source in self.sources.values():
            if (
                source.tenant_id == tenant_id
                and source.name == name
            ):
                return source

        return None

    def list_for_tenant(
        self,
        tenant_id,
    ):
        return [
            source
            for source in self.sources.values()
            if source.tenant_id == tenant_id
        ]


def make_source(
    *,
    source_id="src-1",
    tenant_id="tenant-a",
    name="NOEMIE Production",
):
    return DataSource(
        source_id=source_id,
        tenant_id=tenant_id,
        name=name,
        source_type="sql_server",
    )


def test_create_and_get_source():
    repository = InMemoryDataSourceRepository()
    service = DataCatalogService(repository)

    created = service.create_source(
        make_source()
    )

    loaded = service.get_source(
        tenant_id="tenant-a",
        source_id="src-1",
    )

    assert loaded == created


def test_same_source_id_can_exist_in_different_tenants():
    repository = InMemoryDataSourceRepository()
    service = DataCatalogService(repository)

    service.create_source(
        make_source(
            tenant_id="tenant-a",
        )
    )

    service.create_source(
        make_source(
            tenant_id="tenant-b",
        )
    )

    assert len(
        service.list_sources(
            tenant_id="tenant-a"
        )
    ) == 1

    assert len(
        service.list_sources(
            tenant_id="tenant-b"
        )
    ) == 1


def test_same_name_is_rejected_inside_same_tenant():
    repository = InMemoryDataSourceRepository()
    service = DataCatalogService(repository)

    service.create_source(
        make_source(
            source_id="src-1",
        )
    )

    with pytest.raises(
        ValueError,
        match="same name",
    ):
        service.create_source(
            make_source(
                source_id="src-2",
            )
        )


def test_same_name_is_allowed_between_tenants():
    repository = InMemoryDataSourceRepository()
    service = DataCatalogService(repository)

    service.create_source(
        make_source(
            tenant_id="tenant-a",
        )
    )

    service.create_source(
        make_source(
            source_id="src-2",
            tenant_id="tenant-b",
        )
    )

    assert len(
        service.list_sources(
            tenant_id="tenant-a"
        )
    ) == 1

    assert len(
        service.list_sources(
            tenant_id="tenant-b"
        )
    ) == 1


def test_cross_tenant_read_is_impossible():
    repository = InMemoryDataSourceRepository()
    service = DataCatalogService(repository)

    service.create_source(
        make_source(
            tenant_id="tenant-a",
        )
    )

    with pytest.raises(
        LookupError,
        match="not found",
    ):
        service.get_source(
            tenant_id="tenant-b",
            source_id="src-1",
        )
