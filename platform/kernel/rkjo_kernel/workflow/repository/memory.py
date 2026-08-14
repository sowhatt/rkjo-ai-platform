from __future__ import annotations

from copy import deepcopy

from rkjo_kernel.workflow.models.workflow_execution import WorkflowExecution


class InMemoryWorkflowRepository:
    """In-memory WorkflowRepository implementation.

    Objects are copied on both writes and reads so callers cannot
    accidentally mutate the repository's internal state.
    """

    def __init__(self) -> None:
        self._executions: dict[str, WorkflowExecution] = {}

    def save(self, execution: WorkflowExecution) -> None:
        self._executions[execution.execution_id] = deepcopy(execution)

    def get(self, execution_id: str) -> WorkflowExecution | None:
        execution = self._executions.get(execution_id)

        if execution is None:
            return None

        return deepcopy(execution)

    def delete(self, execution_id: str) -> None:
        self._executions.pop(execution_id, None)

    def exists(self, execution_id: str) -> bool:
        return execution_id in self._executions

    def list_all(self) -> list[WorkflowExecution]:
        return [
            deepcopy(execution)
            for execution in self._executions.values()
        ]
