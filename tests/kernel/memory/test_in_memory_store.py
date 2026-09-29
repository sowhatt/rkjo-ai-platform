from __future__ import annotations

from rkjo_kernel.memory import (
    InMemoryMemoryStore,
    MemoryItem,
    MemoryPort,
    MemoryQuery,
    MemoryScope,
    MemoryType,
)


def mission_memory(
    *,
    content: str = "Learner struggles with fractions",
    tenant_id: str = "tenant-a",
    mission_id: str = "mission-123",
    importance: float = 0.5,
    memory_type: MemoryType = MemoryType.OBSERVATION,
    metadata: dict | None = None,
) -> MemoryItem:
    return MemoryItem(
        content=content,
        tenant_id=tenant_id,
        scope=MemoryScope.MISSION,
        mission_id=mission_id,
        importance=importance,
        memory_type=memory_type,
        metadata=metadata or {},
    )


def test_store_implements_memory_port() -> None:
    assert isinstance(InMemoryMemoryStore(), MemoryPort)


def test_write_and_get_memory() -> None:
    store = InMemoryMemoryStore()
    item = mission_memory()

    stored = store.write(item)

    assert stored is item
    assert (
        store.get(item.memory_id, tenant_id="tenant-a")
        == item
    )


def test_get_is_tenant_isolated() -> None:
    store = InMemoryMemoryStore()
    item = store.write(mission_memory())

    assert (
        store.get(item.memory_id, tenant_id="tenant-b")
        is None
    )


def test_search_is_tenant_isolated() -> None:
    store = InMemoryMemoryStore()

    store.write(
        mission_memory(
            content="Tenant A fractions",
            tenant_id="tenant-a",
        )
    )
    store.write(
        mission_memory(
            content="Tenant B fractions",
            tenant_id="tenant-b",
        )
    )

    results = store.search(
        MemoryQuery(tenant_id="tenant-a")
    )

    assert len(results) == 1
    assert results[0].tenant_id == "tenant-a"


def test_search_filters_by_mission() -> None:
    store = InMemoryMemoryStore()

    expected = store.write(
        mission_memory(mission_id="mission-123")
    )
    store.write(
        mission_memory(mission_id="mission-999")
    )

    results = store.search(
        MemoryQuery(
            tenant_id="tenant-a",
            mission_id="mission-123",
        )
    )

    assert results == [expected]


def test_search_filters_by_scope() -> None:
    store = InMemoryMemoryStore()

    mission = store.write(mission_memory())

    store.write(
        MemoryItem(
            content="Learner profile",
            tenant_id="tenant-a",
            scope=MemoryScope.ENTITY,
            entity_id="learner-123",
        )
    )

    results = store.search(
        MemoryQuery(
            tenant_id="tenant-a",
            scopes=(MemoryScope.MISSION,),
        )
    )

    assert results == [mission]


def test_search_filters_by_entity() -> None:
    store = InMemoryMemoryStore()

    expected = store.write(
        MemoryItem(
            content="Needs visual explanations",
            tenant_id="tenant-a",
            scope=MemoryScope.ENTITY,
            entity_id="learner-123",
        )
    )

    store.write(
        MemoryItem(
            content="Different learner",
            tenant_id="tenant-a",
            scope=MemoryScope.ENTITY,
            entity_id="learner-456",
        )
    )

    results = store.search(
        MemoryQuery(
            tenant_id="tenant-a",
            entity_id="learner-123",
        )
    )

    assert results == [expected]


def test_search_filters_by_memory_type() -> None:
    store = InMemoryMemoryStore()

    expected = store.write(
        mission_memory(
            memory_type=MemoryType.DECISION,
            content="Use visual examples",
        )
    )

    store.write(
        mission_memory(
            memory_type=MemoryType.OBSERVATION,
            content="Learner hesitates",
        )
    )

    results = store.search(
        MemoryQuery(
            tenant_id="tenant-a",
            memory_types=(MemoryType.DECISION,),
        )
    )

    assert results == [expected]


def test_search_supports_case_insensitive_text() -> None:
    store = InMemoryMemoryStore()

    expected = store.write(
        mission_memory(
            content="Learner struggles with FRACTIONS"
        )
    )
    store.write(
        mission_memory(
            content="Learner understands geometry"
        )
    )

    results = store.search(
        MemoryQuery(
            tenant_id="tenant-a",
            text="fractions",
        )
    )

    assert results == [expected]


def test_search_filters_by_min_importance() -> None:
    store = InMemoryMemoryStore()

    expected = store.write(
        mission_memory(
            content="Critical learning difficulty",
            importance=0.9,
        )
    )
    store.write(
        mission_memory(
            content="Minor observation",
            importance=0.2,
        )
    )

    results = store.search(
        MemoryQuery(
            tenant_id="tenant-a",
            min_importance=0.8,
        )
    )

    assert results == [expected]


def test_search_filters_by_metadata() -> None:
    store = InMemoryMemoryStore()

    expected = store.write(
        mission_memory(
            metadata={
                "source": "teacher",
                "subject": "math",
            }
        )
    )

    store.write(
        mission_memory(
            content="Automatic observation",
            metadata={"source": "agent"},
        )
    )

    results = store.search(
        MemoryQuery(
            tenant_id="tenant-a",
            metadata={"source": "teacher"},
        )
    )

    assert results == [expected]


def test_search_orders_by_importance() -> None:
    store = InMemoryMemoryStore()

    low = store.write(
        mission_memory(
            content="Low importance",
            importance=0.2,
        )
    )
    high = store.write(
        mission_memory(
            content="High importance",
            importance=0.9,
        )
    )
    medium = store.write(
        mission_memory(
            content="Medium importance",
            importance=0.5,
        )
    )

    results = store.search(
        MemoryQuery(tenant_id="tenant-a")
    )

    assert results == [high, medium, low]


def test_search_respects_limit() -> None:
    store = InMemoryMemoryStore()

    for index in range(5):
        store.write(
            mission_memory(
                content=f"Memory {index}",
                importance=index / 10,
            )
        )

    results = store.search(
        MemoryQuery(
            tenant_id="tenant-a",
            limit=2,
        )
    )

    assert len(results) == 2


def test_delete_removes_memory() -> None:
    store = InMemoryMemoryStore()
    item = store.write(mission_memory())

    deleted = store.delete(
        item.memory_id,
        tenant_id="tenant-a",
    )

    assert deleted is True
    assert (
        store.get(item.memory_id, tenant_id="tenant-a")
        is None
    )


def test_delete_cannot_cross_tenant_boundary() -> None:
    store = InMemoryMemoryStore()
    item = store.write(mission_memory())

    deleted = store.delete(
        item.memory_id,
        tenant_id="tenant-b",
    )

    assert deleted is False
    assert (
        store.get(item.memory_id, tenant_id="tenant-a")
        == item
    )


def test_delete_unknown_memory_returns_false() -> None:
    store = InMemoryMemoryStore()

    assert (
        store.delete(
            "unknown-memory",
            tenant_id="tenant-a",
        )
        is False
    )
