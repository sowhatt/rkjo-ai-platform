from __future__ import annotations

from typing import Any

from rkjo_kernel.mission.execution_context import ExecutionContext

from .models import MemoryItem, MemoryQuery, MemoryScope, MemoryType
from .port import MemoryPort


class MissionMemoryService:
    """Mission-scoped memory facade bound to ExecutionContext."""

    def __init__(self, store: MemoryPort) -> None:
        self._store = store

    def remember(
        self,
        *,
        context: ExecutionContext,
        content: str,
        memory_type: MemoryType = MemoryType.FACT,
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryItem:
        tenant_id = self._required_context_value(context.tenant_id, "tenant_id")
        mission_id = self._required_context_value(context.mission_id, "mission_id")

        memory_metadata = dict(metadata or {})
        memory_metadata.update(
            {
                key: value
                for key, value in {
                    "trace_id": context.trace_id,
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
            scope=MemoryScope.MISSION,
            memory_type=memory_type,
            mission_id=mission_id,
            execution_id=context.workflow_execution_id,
            user_id=context.user_id,
            importance=importance,
            metadata=memory_metadata,
        )
        return self._store.write(item)

    def recall(
        self,
        *,
        context: ExecutionContext,
        text: str | None = None,
        memory_types: tuple[MemoryType, ...] = (),
        min_importance: float | None = None,
        limit: int = 20,
    ) -> list[MemoryItem]:
        tenant_id = self._required_context_value(context.tenant_id, "tenant_id")
        mission_id = self._required_context_value(context.mission_id, "mission_id")

        return self._store.search(
            MemoryQuery(
                tenant_id=tenant_id,
                scopes=(MemoryScope.MISSION,),
                memory_types=memory_types,
                mission_id=mission_id,
                text=text,
                min_importance=min_importance,
                limit=limit,
            )
        )

    @staticmethod
    def _required_context_value(value: str | None, field_name: str) -> str:
        if value is None or not value.strip():
            raise ValueError(
                f"ExecutionContext {field_name} is required for mission memory"
            )
        return value.strip()
