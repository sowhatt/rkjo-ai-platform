from __future__ import annotations

from dataclasses import replace

import pytest

from rkjo_kernel.memory import (
    ContextBudget,
    ContextBudgetEnforcer,
    ContextEngine,
    InMemoryMemoryStore,
    MemoryItem,
    MemoryScope,
    MissionMemoryService,
)
from rkjo_kernel.mission.execution_context import ExecutionContext


def memory(content: str, importance: float = 0.5) -> MemoryItem:
    return MemoryItem(
        content=content,
        tenant_id="tenant-a",
        scope=MemoryScope.MISSION,
        mission_id="mission-1",
        importance=importance,
    )


def context() -> ExecutionContext:
    return ExecutionContext(
        mission_id="mission-1",
        trace_id="trace-1",
        tenant_id="tenant-a",
    )


def test_budget_limits_number_of_items() -> None:
    enforcer = ContextBudgetEnforcer()
    items = (memory("one"), memory("two"), memory("three"))

    selected = enforcer.apply(
        items,
        budget=ContextBudget(max_items=2),
    )

    assert selected == items[:2]


def test_budget_limits_total_characters() -> None:
    enforcer = ContextBudgetEnforcer()
    first = memory("12345")
    second = memory("123456")
    third = memory("1234")

    selected = enforcer.apply(
        (first, second, third),
        budget=ContextBudget(max_characters=9),
    )

    assert selected == (first, third)


def test_budget_combines_item_and_character_limits() -> None:
    enforcer = ContextBudgetEnforcer()
    items = (memory("1234"), memory("5678"), memory("90"))

    selected = enforcer.apply(
        items,
        budget=ContextBudget(max_items=2, max_characters=10),
    )

    assert selected == items[:2]


def test_oversized_item_is_skipped_without_blocking_following_item() -> None:
    enforcer = ContextBudgetEnforcer()
    oversized = memory("x" * 20)
    fitting = memory("ok")

    selected = enforcer.apply(
        (oversized, fitting),
        budget=ContextBudget(max_characters=5),
    )

    assert selected == (fitting,)


def test_budget_preserves_input_order() -> None:
    enforcer = ContextBudgetEnforcer()
    high = memory("high", importance=1.0)
    low = memory("low", importance=0.1)

    selected = enforcer.apply(
        (high, low),
        budget=ContextBudget(max_items=2),
    )

    assert selected == (high, low)


def test_context_engine_applies_budget_after_memory_collection() -> None:
    store = InMemoryMemoryStore()
    mission = MissionMemoryService(store)
    engine = ContextEngine(store)

    mission.remember(context=context(), content="first", importance=0.9)
    mission.remember(context=context(), content="second", importance=0.8)

    package = engine.build(
        context=context(),
        budget=ContextBudget(max_items=1),
    )

    assert len(package.items) == 1
    assert package.items[0].content == "first"


def test_context_engine_applies_budget_after_selection() -> None:
    store = InMemoryMemoryStore()
    mission = MissionMemoryService(store)
    engine = ContextEngine(store)

    mission.remember(
        context=context(),
        content="geometry note",
        importance=1.0,
    )
    relevant = mission.remember(
        context=context(),
        content="visual fractions",
        importance=0.5,
    )

    package = engine.build(
        context=context(),
        query="visual fractions",
        budget=ContextBudget(max_items=1),
    )

    assert package.items == (relevant,)


def test_unbounded_budget_keeps_all_items() -> None:
    enforcer = ContextBudgetEnforcer()
    items = (memory("one"), memory("two"))

    assert enforcer.apply(items, budget=ContextBudget()) == items


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_items", 0),
        ("max_items", -1),
        ("max_characters", 0),
        ("max_characters", -1),
    ],
)
def test_budget_rejects_non_positive_limits(field: str, value: int) -> None:
    budget = ContextBudget()
    with pytest.raises(ValueError):
        replace(budget, **{field: value})
