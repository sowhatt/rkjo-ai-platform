from __future__ import annotations

from typing import Any

from rkjo_kernel.mission.execution_context import ExecutionContext

from .models import MemoryItem, MemoryQuery, MemoryScope, MemoryType
from .port import MemoryPort


class EntityMemoryService:
    """Entity-scoped memory facade bound to an ExecutionContext tenant."""

    def __init__(self, store: MemoryPort) -> None:
        self._store = store

    def remember(
        self,
        *,
        context: ExecutionContext,
        entity_id: str,
        content: str,
        memory_type: MemoryType = MemoryType.FACT,
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryItem:
        tenant_id = self._required(context.tenant_id, "tenant_id")
        normalized_entity_id = self._required(entity_id, "entity_id")

        memory_metadata = dict(metadata or {})
        memory_metadata.update(
            {
                key: value
                for key, value in {
                    "trace_id": context.trace_id,
                    "mission_id": context.mission_id,
                    "workflow_execution_id": context.workflow_execution_id,
                    "workflow_step_id": context.step_id,
                    "agent_id": context.agent_id,
                    "capability_name": context.capability_name,
                    "tool_call_id": context.tool_call_id,
                    "correlation_id": context.correlation_id,
                    "request_id": context.request_id,
                    "parent_span_id": context.parent_span_id,
                }.items()
                if value is not None
            }
        )

        item = MemoryItem(
            content=content,
            tenant_id=tenant_id,
            scope=MemoryScope.ENTITY,
            memory_type=memory_type,
            mission_id=context.mission_id,
            execution_id=context.workflow_execution_id,
            user_id=context.user_id,
            entity_id=normalized_entity_id,
            importance=importance,
            metadata=memory_metadata,
        )
        return self._store.write(item)

    def recall(
        self,
        *,
        context: ExecutionContext,
        entity_id: str,
        text: str | None = None,
        memory_types: tuple[MemoryType, ...] = (),
        min_importance: float | None = None,
        limit: int = 20,
    ) -> list[MemoryItem]:
        tenant_id = self._required(context.tenant_id, "tenant_id")
        normalized_entity_id = self._required(entity_id, "entity_id")

        return self._store.search(
            MemoryQuery(
                tenant_id=tenant_id,
                scopes=(MemoryScope.ENTITY,),
                memory_types=memory_types,
                entity_id=normalized_entity_id,
                text=text,
                min_importance=min_importance,
                limit=limit,
            )
        )

    @staticmethod
    def _required(value: str | None, field_name: str) -> str:
        if value is None or not value.strip():
            raise ValueError(f"{field_name} must not be empty")
        return value.strip()
