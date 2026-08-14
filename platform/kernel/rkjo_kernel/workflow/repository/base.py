from __future__ import annotations

from typing import Protocol

from rkjo_kernel.workflow.models.workflow_execution import WorkflowExecution


class WorkflowRepository(Protocol):
    """Persistence contract for workflow executions."""

    def save(self, execution: WorkflowExecution) -> None:
        ...

    def get(self, execution_id: str) -> WorkflowExecution | None:
        ...

    def delete(self, execution_id: str) -> None:
        ...

    def exists(self, execution_id: str) -> bool:
        ...

    def list_all(self) -> list[WorkflowExecution]:
        ...
