from __future__ import annotations

from dataclasses import dataclass

from rkjo_kernel.mission.execution_context import ExecutionContext

from .budget import ContextBudget, ContextBudgetEnforcer
from .models import MemoryItem, MemoryQuery, MemoryScope
from .port import MemoryPort
from .rag_bridge import KnowledgeContextItem, RAGContextBridge
from .selection import ContextSelectionPolicy, ContextSelector


@dataclass(frozen=True, slots=True)
class ContextPackage:
    """Selected memory context prepared for an agent execution."""

    tenant_id: str
    mission_id: str
    trace_id: str
    items: tuple[MemoryItem, ...]
    entity_id: str | None = None
    knowledge_items: tuple[KnowledgeContextItem, ...] = ()

    @property
    def mission_items(self) -> tuple[MemoryItem, ...]:
        return tuple(
            item for item in self.items
            if item.scope is MemoryScope.MISSION
        )

    @property
    def entity_items(self) -> tuple[MemoryItem, ...]:
        return tuple(
            item for item in self.items
            if item.scope is MemoryScope.ENTITY
        )


class ContextEngine:
    """Build a deterministic context package from shared memory."""

    def __init__(
        self,
        store: MemoryPort,
        selector: ContextSelector | None = None,
        budget_enforcer: ContextBudgetEnforcer | None = None,
        rag_bridge: RAGContextBridge | None = None,
    ) -> None:
        self._store = store
        self._selector = selector or ContextSelector()
        self._budget_enforcer = budget_enforcer or ContextBudgetEnforcer()
        self._rag_bridge = rag_bridge

    def build(
        self,
        *,
        context: ExecutionContext,
        entity_id: str | None = None,
        mission_limit: int = 20,
        entity_limit: int = 20,
        query: str | None = None,
        selection_policy: ContextSelectionPolicy | None = None,
        budget: ContextBudget | None = None,
        knowledge_limit: int = 5,
        knowledge_filters=None,
    ) -> ContextPackage:
        tenant_id = self._required(context.tenant_id, "tenant_id")
        mission_id = self._required(context.mission_id, "mission_id")

        mission_items = self._store.search(
            MemoryQuery(
                tenant_id=tenant_id,
                scopes=(MemoryScope.MISSION,),
                mission_id=mission_id,
                limit=mission_limit,
            )
        )

        normalized_entity_id: str | None = None
        entity_items: list[MemoryItem] = []
        if entity_id is not None:
            normalized_entity_id = self._required(entity_id, "entity_id")
            entity_items = self._store.search(
                MemoryQuery(
                    tenant_id=tenant_id,
                    scopes=(MemoryScope.ENTITY,),
                    entity_id=normalized_entity_id,
                    limit=entity_limit,
                )
            )

        items = self._deduplicate(
            (*mission_items, *entity_items)
        )
        if query is not None or selection_policy is not None:
            items = self._selector.select(
                items,
                query=query,
                policy=selection_policy,
            )

        if budget is not None:
            items = self._budget_enforcer.apply(items, budget=budget)

        knowledge_items: tuple[KnowledgeContextItem, ...] = ()
        if self._rag_bridge is not None and query is not None and query.strip():
            knowledge_items = self._rag_bridge.retrieve(
                query,
                limit=knowledge_limit,
                filters=knowledge_filters,
            )

        return ContextPackage(
            tenant_id=tenant_id,
            mission_id=mission_id,
            trace_id=context.trace_id,
            entity_id=normalized_entity_id,
            items=items,
            knowledge_items=knowledge_items,
        )

    @staticmethod
    def _deduplicate(
        items: tuple[MemoryItem, ...],
    ) -> tuple[MemoryItem, ...]:
        seen: set[str] = set()
        selected: list[MemoryItem] = []

        for item in items:
            if item.memory_id in seen:
                continue
            seen.add(item.memory_id)
            selected.append(item)

        return tuple(selected)

    @staticmethod
    def _required(value: str | None, field_name: str) -> str:
        if value is None or not value.strip():
            raise ValueError(f"{field_name} must not be empty")
        return value.strip()
