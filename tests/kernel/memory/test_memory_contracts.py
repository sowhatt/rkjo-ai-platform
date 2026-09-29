from __future__ import annotations

import pytest

from rkjo_kernel.memory import (
    MemoryItem,
    MemoryPort,
    MemoryQuery,
    MemoryScope,
    MemoryType,
)


def test_memory_item_supports_mission_scope() -> None:
    item = MemoryItem(
        content="The learner struggles with fractions.",
        tenant_id="tenant-a",
        scope=MemoryScope.MISSION,
        mission_id="mission-123",
        memory_type=MemoryType.OBSERVATION,
    )

    assert item.tenant_id == "tenant-a"
    assert item.mission_id == "mission-123"
    assert item.scope is MemoryScope.MISSION
    assert item.memory_type is MemoryType.OBSERVATION
    assert item.memory_id


def test_memory_item_supports_entity_scope() -> None:
    item = MemoryItem(
        content="Learner confuses numerator and denominator.",
        tenant_id="tenant-a",
        scope=MemoryScope.ENTITY,
        entity_id="learner-123",
        domain="education",
    )

    assert item.entity_id == "learner-123"
    assert item.domain == "education"


@pytest.mark.parametrize(
    ("scope", "expected_message"),
    [
        (MemoryScope.MISSION, "mission_id"),
        (MemoryScope.EXECUTION, "execution_id"),
        (MemoryScope.USER, "user_id"),
        (MemoryScope.DOMAIN, "domain"),
        (MemoryScope.ENTITY, "entity_id"),
    ],
)
def test_scoped_memory_requires_scope_identifier(
    scope: MemoryScope,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        MemoryItem(
            content="Important information",
            tenant_id="tenant-a",
            scope=scope,
        )


def test_tenant_scope_does_not_require_additional_identifier() -> None:
    item = MemoryItem(
        content="Tenant-wide information",
        tenant_id="tenant-a",
        scope=MemoryScope.TENANT,
    )

    assert item.scope is MemoryScope.TENANT


def test_memory_item_rejects_empty_tenant() -> None:
    with pytest.raises(ValueError, match="tenant_id"):
        MemoryItem(
            content="Information",
            tenant_id="",
            scope=MemoryScope.TENANT,
        )


def test_memory_item_rejects_empty_content() -> None:
    with pytest.raises(ValueError, match="content"):
        MemoryItem(
            content="   ",
            tenant_id="tenant-a",
            scope=MemoryScope.TENANT,
        )


@pytest.mark.parametrize("importance", [-0.01, 1.01])
def test_memory_item_rejects_invalid_importance(
    importance: float,
) -> None:
    with pytest.raises(ValueError, match="importance"):
        MemoryItem(
            content="Information",
            tenant_id="tenant-a",
            scope=MemoryScope.TENANT,
            importance=importance,
        )


def test_memory_query_is_tenant_scoped() -> None:
    query = MemoryQuery(
        tenant_id="tenant-a",
        scopes=(MemoryScope.MISSION, MemoryScope.ENTITY),
        mission_id="mission-123",
        entity_id="learner-123",
        text="fractions",
        limit=5,
    )

    assert query.tenant_id == "tenant-a"
    assert query.limit == 5
    assert MemoryScope.MISSION in query.scopes
    assert MemoryScope.ENTITY in query.scopes


def test_memory_query_rejects_invalid_limit() -> None:
    with pytest.raises(ValueError, match="limit"):
        MemoryQuery(
            tenant_id="tenant-a",
            limit=0,
        )


def test_memory_query_rejects_invalid_min_importance() -> None:
    with pytest.raises(ValueError, match="min_importance"):
        MemoryQuery(
            tenant_id="tenant-a",
            min_importance=2.0,
        )


def test_memory_port_is_runtime_checkable() -> None:
    class FakeMemoryStore:
        def write(self, item):
            return item

        def get(self, memory_id, *, tenant_id):
            return None

        def search(self, query):
            return []

        def delete(self, memory_id, *, tenant_id):
            return False

    assert isinstance(FakeMemoryStore(), MemoryPort)
