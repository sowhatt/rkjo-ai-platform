from __future__ import annotations

import pytest

from rkjo_kernel.memory.in_memory import InMemoryMemoryStore
from rkjo_kernel.memory.mission_memory import MissionMemoryService
from rkjo_kernel.memory.models import MemoryScope, MemoryType
from rkjo_kernel.mission.execution_context import ExecutionContext


def execution_context(
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
        tool_call_id="tool-123",
        tenant_id=tenant_id,
        user_id="user-123",
        correlation_id="correlation-123",
        request_id="request-123",
    )


def test_remember_creates_mission_memory_from_context() -> None:
    service = MissionMemoryService(InMemoryMemoryStore())

    item = service.remember(
        context=execution_context(),
        content="Learner needs visual explanations",
        memory_type=MemoryType.OBSERVATION,
        importance=0.8,
    )

    assert item.tenant_id == "tenant-a"
    assert item.scope is MemoryScope.MISSION
    assert item.mission_id == "mission-123"
    assert item.execution_id == "execution-123"
    assert item.user_id == "user-123"
    assert item.memory_type is MemoryType.OBSERVATION
    assert item.importance == 0.8


def test_remember_propagates_execution_metadata() -> None:
    service = MissionMemoryService(InMemoryMemoryStore())

    item = service.remember(
        context=execution_context(),
        content="Use a visual fraction model",
    )

    assert item.metadata["trace_id"] == "trace-123"
    assert item.metadata["workflow_execution_id"] == "execution-123"
    assert item.metadata["workflow_step_id"] == "step-1"
    assert item.metadata["agent_id"] == "education.tutor"
    assert item.metadata["capability_name"] == "education.explain"
    assert item.metadata["tool_call_id"] == "tool-123"


def test_context_identifiers_override_caller_metadata() -> None:
    service = MissionMemoryService(InMemoryMemoryStore())

    item = service.remember(
        context=execution_context(),
        content="Canonical context wins",
        metadata={
            "trace_id": "caller-trace",
            "workflow_execution_id": "caller-execution",
            "source": "teacher",
        },
    )

    assert item.metadata["trace_id"] == "trace-123"
    assert item.metadata["workflow_execution_id"] == "execution-123"
    assert item.metadata["source"] == "teacher"


def test_recall_returns_only_current_mission() -> None:
    store = InMemoryMemoryStore()
    service = MissionMemoryService(store)

    service.remember(
        context=execution_context(mission_id="mission-123"),
        content="Fractions need visual support",
    )
    service.remember(
        context=execution_context(mission_id="mission-999"),
        content="Other mission",
    )

    results = service.recall(
        context=execution_context(mission_id="mission-123"),
    )

    assert len(results) == 1
    assert results[0].mission_id == "mission-123"


def test_recall_applies_filters() -> None:
    store = InMemoryMemoryStore()
    service = MissionMemoryService(store)
    context = execution_context()

    service.remember(
        context=context,
        content="Fractions visual model",
        memory_type=MemoryType.DECISION,
        importance=0.9,
    )
    service.remember(
        context=context,
        content="Fractions minor note",
        memory_type=MemoryType.OBSERVATION,
        importance=0.2,
    )
    service.remember(
        context=context,
        content="Geometry decision",
        memory_type=MemoryType.DECISION,
        importance=1.0,
    )

    results = service.recall(
        context=context,
        text="fractions",
        memory_types=(MemoryType.DECISION,),
        min_importance=0.8,
        limit=1,
    )

    assert len(results) == 1
    assert results[0].content == "Fractions visual model"


def test_recall_is_tenant_isolated() -> None:
    store = InMemoryMemoryStore()
    service = MissionMemoryService(store)

    service.remember(
        context=execution_context(
            tenant_id="tenant-a",
            mission_id="shared-mission",
        ),
        content="Tenant A memory",
    )
    service.remember(
        context=execution_context(
            tenant_id="tenant-b",
            mission_id="shared-mission",
        ),
        content="Tenant B memory",
    )

    results = service.recall(
        context=execution_context(
            tenant_id="tenant-a",
            mission_id="shared-mission",
        )
    )

    assert [item.content for item in results] == ["Tenant A memory"]


def test_remember_requires_tenant_id() -> None:
    service = MissionMemoryService(InMemoryMemoryStore())

    with pytest.raises(ValueError, match="tenant_id"):
        service.remember(
            context=execution_context(tenant_id=None),
            content="Must fail",
        )


def test_recall_requires_tenant_id() -> None:
    service = MissionMemoryService(InMemoryMemoryStore())

    with pytest.raises(ValueError, match="tenant_id"):
        service.recall(context=execution_context(tenant_id=None))
