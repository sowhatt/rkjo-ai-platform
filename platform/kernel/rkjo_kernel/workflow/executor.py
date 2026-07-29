"""Sequential execution service for workflows."""

from __future__ import annotations

from typing import Any

from rkjo_kernel.workflow.agent_execution_adapter import (
    AgentExecutionAdapter,
)
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.exceptions import (
    InvalidWorkflowTransitionError,
)
from rkjo_kernel.workflow.execution_result import ExecutionResult
from rkjo_kernel.workflow.models.workflow_execution import (
    WorkflowExecution,
)
from rkjo_kernel.workflow.models.workflow_status import WorkflowStatus


class WorkflowExecutor:
    """Execute sequential workflow steps through an agent adapter.

    The executor coordinates the execution loop while delegating:

    - lifecycle changes to WorkflowEngine;
    - agent invocation to AgentExecutionAdapter;
    - execution outcomes to ExecutionResult.
    """

    def __init__(
        self,
        *,
        adapter: AgentExecutionAdapter,
        engine: WorkflowEngine | None = None,
    ) -> None:
        self.adapter = adapter
        self.engine = engine or WorkflowEngine()

    def execute(
        self,
        execution: WorkflowExecution,
    ) -> WorkflowExecution:
        """Execute all remaining steps of a workflow.

        A pending workflow is started automatically.

        A running workflow resumes from its first remaining
        pending step.
        """
        if execution.status == WorkflowStatus.PENDING:
            self.engine.start(execution)
        elif execution.status != WorkflowStatus.RUNNING:
            raise InvalidWorkflowTransitionError(
                "Only a pending or running workflow execution "
                "can be executed."
            )

        while execution.status == WorkflowStatus.RUNNING:
            result = self.execute_next(execution)

            if result is None:
                self.engine.complete(execution)
                break

            if result.is_failure:
                break

        return execution

    def execute_next(
        self,
        execution: WorkflowExecution,
    ) -> ExecutionResult | None:
        """Execute the next pending workflow step.

        Return None when no pending step remains.

        Adapter exceptions and invalid adapter responses are converted
        into failed ExecutionResult objects so the workflow lifecycle
        remains consistent.
        """
        if execution.status != WorkflowStatus.RUNNING:
            raise InvalidWorkflowTransitionError(
                "The next step can only be executed while "
                "the workflow is running."
            )

        step = self.engine.start_next_step(execution)

        if step is None:
            return None

        result = self._invoke_adapter(
            step=step,
            execution=execution,
        )

        self._record_result_metadata(
            execution=execution,
            step_id=step.step_id,
            result=result,
        )

        if result.success:
            self.engine.complete_current_step(
                execution,
                output=result.output,
            )
        else:
            self.engine.fail_current_step(
                execution,
                error=result.error or "Agent execution failed.",
            )

        return result

    def _invoke_adapter(
        self,
        *,
        step: Any,
        execution: WorkflowExecution,
    ) -> ExecutionResult:
        """Invoke the adapter and normalize technical failures."""
        try:
            result = self.adapter.execute(
                step=step,
                context=execution.context,
            )
        except Exception as exc:
            message = str(exc).strip() or exc.__class__.__name__

            return ExecutionResult.failed(
                error=f"{exc.__class__.__name__}: {message}",
                metadata={
                    "exception_type": exc.__class__.__name__,
                },
            )

        if not isinstance(result, ExecutionResult):
            return ExecutionResult.failed(
                error=(
                    "AgentExecutionAdapter must return "
                    "an ExecutionResult."
                ),
                metadata={
                    "returned_type": type(result).__name__,
                },
            )

        return result

    @staticmethod
    def _record_result_metadata(
        *,
        execution: WorkflowExecution,
        step_id: str,
        result: ExecutionResult,
    ) -> None:
        """Store technical execution information in the context."""
        step_results = execution.context.metadata.get(
            "step_results"
        )

        if not isinstance(step_results, dict):
            step_results = {}
            execution.context.metadata["step_results"] = (
                step_results
            )

        step_results[step_id] = {
            "success": result.success,
            "error": result.error,
            "duration_ms": result.duration_ms,
            "metadata": dict(result.metadata),
        }
