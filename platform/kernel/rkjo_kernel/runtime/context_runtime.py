from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rkjo_kernel.memory import ContextBudget, ContextEngine, ContextPackage
from rkjo_kernel.mission.execution_context import ExecutionContext


@dataclass(frozen=True, slots=True)
class RuntimeContextRequest:
    query: str | None = None
    entity_id: str | None = None
    mission_limit: int = 20
    entity_limit: int = 20
    knowledge_limit: int = 5
    budget: ContextBudget | None = None


class AgentContextRuntime:
    """Prepare Memory/RAG context for one real agent execution."""

    def __init__(self, context_engine: ContextEngine) -> None:
        self._context_engine = context_engine

    def prepare(
        self,
        *,
        execution_context: ExecutionContext,
        request: RuntimeContextRequest,
    ) -> ContextPackage:
        return self._context_engine.build(
            context=execution_context,
            entity_id=request.entity_id,
            mission_limit=request.mission_limit,
            entity_limit=request.entity_limit,
            query=request.query,
            budget=request.budget,
            knowledge_limit=request.knowledge_limit,
        )

    @staticmethod
    def inject(
        metadata: dict[str, Any],
        package: ContextPackage,
    ) -> None:
        metadata["context_package"] = package
