from __future__ import annotations

from dataclasses import replace

import pytest

from rkjo_kernel.memory import (
    ContextEngine,
    ContextSelectionPolicy,
    ContextSelector,
    EntityMemoryService,
    InMemoryMemoryStore,
    MemoryItem,
    MemoryScope,
    MissionMemoryService,
)
from rkjo_kernel.mission.execution_context import ExecutionContext


def item(
    content: str,
    *,
    importance: float = 0.5,
    scope: MemoryScope = MemoryScope.MISSION,
    entity_id: str | None = None,
) -> MemoryItem:
    return MemoryItem(
        content=content,
        tenant_id="tenant-a",
        scope=scope,
        mission_id="mission-1" if scope is MemoryScope.MISSION else None,
        entity_id=entity_id,
        importance=importance,
    )


def context() -> ExecutionContext:
    return ExecutionContext(
        mission_id="mission-1",
        trace_id="trace-1",
        tenant_id="tenant-a",
    )


def test_selector_prefers_relevant_memory() -> None:
    selector = ContextSelector()
    relevant = item("Learner struggles with visual fractions", importance=0.6)
    irrelevant = item("Learner likes geometry", importance=0.9)

    selected = selector.select(
        (irrelevant, relevant),
        query="visual fractions",
    )

    assert selected[0] == relevant


def test_selector_uses_importance_when_query_is_absent() -> None:
    selector = ContextSelector()
    low = item("Low", importance=0.2)
    high = item("High", importance=0.9)

    assert selector.select((low, high)) == (high, low)


def test_selector_filters_minimum_importance() -> None:
    selector = ContextSelector()
    low = item("Low", importance=0.2)
    high = item("High", importance=0.8)

    selected = selector.select(
        (low, high),
        policy=ContextSelectionPolicy(min_importance=0.5),
    )

    assert selected == (high,)


def test_selector_respects_max_items() -> None:
    selector = ContextSelector()
    items = tuple(
        item(f"Memory {index}", importance=index / 10)
        for index in range(5)
    )

    selected = selector.select(
        items,
        policy=ContextSelectionPolicy(max_items=2),
    )

    assert len(selected) == 2


def test_mission_scope_boost_can_break_equal_score() -> None:
    selector = ContextSelector()
    mission = item(
        "same topic",
        importance=0.5,
        scope=MemoryScope.MISSION,
    )
    entity = item(
        "same topic",
        importance=0.5,
        scope=MemoryScope.ENTITY,
        entity_id="learner-1",
    )

    selected = selector.select(
        (entity, mission),
        query="same topic",
    )

    assert selected[0] == mission


def test_selection_is_case_insensitive() -> None:
    selector = ContextSelector()
    relevant = item("VISUAL Fractions", importance=0.4)
    other = item("Geometry", importance=0.9)

    selected = selector.select(
        (other, relevant),
        query="visual FRACTIONS",
    )

    assert selected[0] == relevant


def test_context_engine_applies_selection() -> None:
    store = InMemoryMemoryStore()
    mission = MissionMemoryService(store)
    entity = EntityMemoryService(store)
    engine = ContextEngine(store)

    mission.remember(
        context=context(),
        content="Geometry note",
        importance=0.9,
    )
    relevant = entity.remember(
        context=context(),
        entity_id="learner-1",
        content="Visual fractions preference",
        importance=0.6,
    )

    package = engine.build(
        context=context(),
        entity_id="learner-1",
        query="visual fractions",
        selection_policy=ContextSelectionPolicy(max_items=1),
    )

    assert package.items == (relevant,)


def test_context_engine_remains_backward_compatible_without_selection() -> None:
    store = InMemoryMemoryStore()
    mission = MissionMemoryService(store)
    entity = EntityMemoryService(store)
    engine = ContextEngine(store)

    mission_item = mission.remember(
        context=context(),
        content="Mission",
        importance=0.1,
    )
    entity_item = entity.remember(
        context=context(),
        entity_id="learner-1",
        content="Entity",
        importance=1.0,
    )

    package = engine.build(
        context=context(),
        entity_id="learner-1",
    )

    assert package.items == (mission_item, entity_item)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_items", 0),
        ("min_importance", -0.1),
        ("min_importance", 1.1),
        ("relevance_weight", -0.1),
    ],
)
def test_policy_rejects_invalid_values(field: str, value: float) -> None:
    policy = ContextSelectionPolicy()
    with pytest.raises(ValueError):
        replace(policy, **{field: value})
