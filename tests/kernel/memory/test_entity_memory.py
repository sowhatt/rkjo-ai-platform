from __future__ import annotations

import pytest

from rkjo_kernel.memory.entity_memory import EntityMemoryService
from rkjo_kernel.memory.in_memory import InMemoryMemoryStore
from rkjo_kernel.memory.models import MemoryScope, MemoryType
from rkjo_kernel.mission.execution_context import ExecutionContext


def context(
    *,
    tenant_id: str | None = "tenant-a",
    mission_id: str = "mission-123",
) -> ExecutionContext:
    return ExecutionContext(
        mission_id=mission_id,
        trace_id="trace-123",
        workflow_execution_id="execution-123",
        step_id="step-1",
        agent_id="education.tutor",
        capability_name="education.explain",
        tenant_id=tenant_id,
        user_id="user-123",
    )


def test_remember_creates_entity_scoped_memory() -> None:
    service = EntityMemoryService(InMemoryMemoryStore())

    item = service.remember(
        context=context(),
        entity_id="learner-123",
        content="Prefers visual explanations",
        memory_type=MemoryType.PREFERENCE,
        importance=0.8,
    )

    assert item.scope is MemoryScope.ENTITY
    assert item.tenant_id == "tenant-a"
    assert item.entity_id == "learner-123"
    assert item.mission_id == "mission-123"
    assert item.execution_id == "execution-123"
    assert item.user_id == "user-123"
    assert item.memory_type is MemoryType.PREFERENCE


def test_entity_memory_survives_mission_boundary() -> None:
    store = InMemoryMemoryStore()
    service = EntityMemoryService(store)

    service.remember(
        context=context(mission_id="mission-1"),
        entity_id="learner-123",
        content="Needs visual fraction models",
    )

    results = service.recall(
        context=context(mission_id="mission-2"),
        entity_id="learner-123",
    )

    assert len(results) == 1
    assert results[0].content == "Needs visual fraction models"
    assert results[0].mission_id == "mission-1"


def test_recall_is_entity_isolated() -> None:
    store = InMemoryMemoryStore()
    service = EntityMemoryService(store)

    service.remember(
        context=context(),
        entity_id="learner-123",
        content="Learner 123 memory",
    )
    service.remember(
        context=context(),
        entity_id="learner-456",
        content="Learner 456 memory",
    )

    results = service.recall(
        context=context(),
        entity_id="learner-123",
    )

    assert [item.content for item in results] == ["Learner 123 memory"]


def test_recall_is_tenant_isolated() -> None:
    store = InMemoryMemoryStore()
    service = EntityMemoryService(store)

    service.remember(
        context=context(tenant_id="tenant-a"),
        entity_id="shared-entity",
        content="Tenant A memory",
    )
    service.remember(
        context=context(tenant_id="tenant-b"),
        entity_id="shared-entity",
        content="Tenant B memory",
    )

    results = service.recall(
        context=context(tenant_id="tenant-a"),
        entity_id="shared-entity",
    )

    assert [item.content for item in results] == ["Tenant A memory"]


def test_recall_applies_filters() -> None:
    store = InMemoryMemoryStore()
    service = EntityMemoryService(store)
    execution_context = context()

    service.remember(
        context=execution_context,
        entity_id="learner-123",
        content="Fractions visual preference",
        memory_type=MemoryType.PREFERENCE,
        importance=0.9,
    )
    service.remember(
        context=execution_context,
        entity_id="learner-123",
        content="Fractions observation",
        memory_type=MemoryType.OBSERVATION,
        importance=0.9,
    )
    service.remember(
        context=execution_context,
        entity_id="learner-123",
        content="Geometry preference",
        memory_type=MemoryType.PREFERENCE,
        importance=1.0,
    )

    results = service.recall(
        context=execution_context,
        entity_id="learner-123",
        text="fractions",
        memory_types=(MemoryType.PREFERENCE,),
        min_importance=0.8,
        limit=1,
    )

    assert len(results) == 1
    assert results[0].content == "Fractions visual preference"


def test_context_metadata_cannot_be_overridden() -> None:
    service = EntityMemoryService(InMemoryMemoryStore())

    item = service.remember(
        context=context(),
        entity_id="learner-123",
        content="Canonical context wins",
        metadata={
            "trace_id": "caller-trace",
            "mission_id": "caller-mission",
            "source": "teacher",
        },
    )

    assert item.metadata["trace_id"] == "trace-123"
    assert item.metadata["mission_id"] == "mission-123"
    assert item.metadata["source"] == "teacher"


def test_entity_id_is_normalized() -> None:
    service = EntityMemoryService(InMemoryMemoryStore())

    item = service.remember(
        context=context(),
        entity_id="  learner-123  ",
        content="Normalized entity",
    )

    assert item.entity_id == "learner-123"


def test_remember_rejects_empty_entity_id() -> None:
    service = EntityMemoryService(InMemoryMemoryStore())

    with pytest.raises(ValueError, match="entity_id"):
        service.remember(
            context=context(),
            entity_id="   ",
            content="Must fail",
        )


def test_recall_requires_tenant_id() -> None:
    service = EntityMemoryService(InMemoryMemoryStore())

    with pytest.raises(ValueError, match="tenant_id"):
        service.recall(
            context=context(tenant_id=None),
            entity_id="learner-123",
        )
