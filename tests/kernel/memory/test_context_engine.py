from __future__ import annotations

import pytest

from rkjo_kernel.memory.context_engine import ContextEngine
from rkjo_kernel.memory.entity_memory import EntityMemoryService
from rkjo_kernel.memory.in_memory import InMemoryMemoryStore
from rkjo_kernel.memory.mission_memory import MissionMemoryService
from rkjo_kernel.memory.models import MemoryScope
from rkjo_kernel.mission.execution_context import ExecutionContext


def context(
    *,
    tenant_id: str | None = "tenant-a",
    mission_id: str = "mission-123",
    trace_id: str = "trace-123",
) -> ExecutionContext:
    return ExecutionContext(
        mission_id=mission_id,
        trace_id=trace_id,
        workflow_execution_id="execution-123",
        tenant_id=tenant_id,
        user_id="user-123",
    )


def test_build_collects_mission_and_entity_memory() -> None:
    store = InMemoryMemoryStore()
    mission = MissionMemoryService(store)
    entity = EntityMemoryService(store)
    engine = ContextEngine(store)
    execution_context = context()

    mission_item = mission.remember(
        context=execution_context,
        content="Current mission observation",
        importance=0.9,
    )
    entity_item = entity.remember(
        context=execution_context,
        entity_id="learner-123",
        content="Persistent learner preference",
        importance=0.8,
    )

    package = engine.build(
        context=execution_context,
        entity_id="learner-123",
    )

    assert package.items == (mission_item, entity_item)
    assert package.mission_items == (mission_item,)
    assert package.entity_items == (entity_item,)


def test_package_carries_canonical_context_identifiers() -> None:
    engine = ContextEngine(InMemoryMemoryStore())

    package = engine.build(
        context=context(
            tenant_id="tenant-a",
            mission_id="mission-123",
            trace_id="trace-xyz",
        ),
        entity_id="  learner-123  ",
    )

    assert package.tenant_id == "tenant-a"
    assert package.mission_id == "mission-123"
    assert package.trace_id == "trace-xyz"
    assert package.entity_id == "learner-123"


def test_build_without_entity_returns_mission_memory_only() -> None:
    store = InMemoryMemoryStore()
    mission = MissionMemoryService(store)
    entity = EntityMemoryService(store)
    engine = ContextEngine(store)
    execution_context = context()

    expected = mission.remember(
        context=execution_context,
        content="Mission memory",
    )
    entity.remember(
        context=execution_context,
        entity_id="learner-123",
        content="Entity memory",
    )

    package = engine.build(context=execution_context)

    assert package.items == (expected,)
    assert package.entity_items == ()


def test_build_ignores_other_missions_and_entities() -> None:
    store = InMemoryMemoryStore()
    mission = MissionMemoryService(store)
    entity = EntityMemoryService(store)
    engine = ContextEngine(store)

    expected_mission = mission.remember(
        context=context(mission_id="mission-123"),
        content="Expected mission",
    )
    mission.remember(
        context=context(mission_id="mission-999"),
        content="Other mission",
    )
    expected_entity = entity.remember(
        context=context(),
        entity_id="learner-123",
        content="Expected entity",
    )
    entity.remember(
        context=context(),
        entity_id="learner-999",
        content="Other entity",
    )

    package = engine.build(
        context=context(mission_id="mission-123"),
        entity_id="learner-123",
    )

    assert package.items == (expected_mission, expected_entity)


def test_build_is_tenant_isolated() -> None:
    store = InMemoryMemoryStore()
    mission = MissionMemoryService(store)
    entity = EntityMemoryService(store)
    engine = ContextEngine(store)

    expected_mission = mission.remember(
        context=context(tenant_id="tenant-a"),
        content="Tenant A mission",
    )
    expected_entity = entity.remember(
        context=context(tenant_id="tenant-a"),
        entity_id="learner-123",
        content="Tenant A entity",
    )
    mission.remember(
        context=context(tenant_id="tenant-b"),
        content="Tenant B mission",
    )
    entity.remember(
        context=context(tenant_id="tenant-b"),
        entity_id="learner-123",
        content="Tenant B entity",
    )

    package = engine.build(
        context=context(tenant_id="tenant-a"),
        entity_id="learner-123",
    )

    assert package.items == (expected_mission, expected_entity)
    assert all(
        item.tenant_id == "tenant-a"
        for item in package.items
    )


def test_mission_memory_precedes_entity_memory() -> None:
    store = InMemoryMemoryStore()
    mission = MissionMemoryService(store)
    entity = EntityMemoryService(store)
    engine = ContextEngine(store)
    execution_context = context()

    entity_item = entity.remember(
        context=execution_context,
        entity_id="learner-123",
        content="Very important entity memory",
        importance=1.0,
    )
    mission_item = mission.remember(
        context=execution_context,
        content="Lower importance mission memory",
        importance=0.1,
    )

    package = engine.build(
        context=execution_context,
        entity_id="learner-123",
    )

    assert package.items == (mission_item, entity_item)


def test_build_respects_per_scope_limits() -> None:
    store = InMemoryMemoryStore()
    mission = MissionMemoryService(store)
    entity = EntityMemoryService(store)
    engine = ContextEngine(store)
    execution_context = context()

    for index in range(3):
        mission.remember(
            context=execution_context,
            content=f"Mission {index}",
            importance=index / 10,
        )
        entity.remember(
            context=execution_context,
            entity_id="learner-123",
            content=f"Entity {index}",
            importance=index / 10,
        )

    package = engine.build(
        context=execution_context,
        entity_id="learner-123",
        mission_limit=1,
        entity_limit=2,
    )

    assert len(package.mission_items) == 1
    assert len(package.entity_items) == 2
    assert len(package.items) == 3


def test_build_requires_tenant_id() -> None:
    engine = ContextEngine(InMemoryMemoryStore())

    with pytest.raises(ValueError, match="tenant_id"):
        engine.build(context=context(tenant_id=None))


def test_build_rejects_empty_entity_id() -> None:
    engine = ContextEngine(InMemoryMemoryStore())

    with pytest.raises(ValueError, match="entity_id"):
        engine.build(
            context=context(),
            entity_id="   ",
        )


def test_context_package_scope_helpers_are_consistent() -> None:
    store = InMemoryMemoryStore()
    mission = MissionMemoryService(store)
    engine = ContextEngine(store)
    expected = mission.remember(
        context=context(),
        content="Mission memory",
    )

    package = engine.build(context=context())

    assert expected.scope is MemoryScope.MISSION
    assert package.mission_items == (expected,)
    assert package.entity_items == ()
