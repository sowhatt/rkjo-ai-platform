"""Application service coordinating workflow executions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from rkjo_kernel.monitoring.metrics import MetricsRegistry
from rkjo_kernel.logging.logger import get_logger
from rkjo_kernel.logging.structured import structured_log

from rkjo_kernel.workflow.models.workflow_context import (
    WorkflowContext,
)
from rkjo_kernel.workflow.models.workflow_definition import (
    WorkflowDefinition,
)
from rkjo_kernel.workflow.models.workflow_execution import (
    WorkflowExecution,
)
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep
from rkjo_kernel.workflow.navigator import WorkflowNavigator
from rkjo_kernel.workflow.repository import WorkflowRepository
from rkjo_kernel.workflow.validator import WorkflowValidator


class WorkflowEngine:
    """Coordinate the lifecycle of sequential workflows."""

    def __init__(
        self,
        *,
        validator: WorkflowValidator | None = None,
        navigator: WorkflowNavigator | None = None,
        repository: WorkflowRepository | None = None,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self.validator = validator or WorkflowValidator()
        self.navigator = navigator or WorkflowNavigator()
        self.repository = repository
        self.metrics = metrics
        self.logger = get_logger(
            "rkjo.workflow.engine"
        )

    def create_execution(
        self,
        definition: WorkflowDefinition,
        *,
        input_data: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        execution_id: str | None = None,
    ) -> WorkflowExecution:
        """Create a new isolated execution from a definition."""
        self.validator.validate_definition(definition)

        execution_definition = deepcopy(definition)

        context = WorkflowContext(
            input_data=dict(input_data or {}),
            metadata=dict(metadata or {}),
        )

        arguments: dict[str, Any] = {
            "definition": execution_definition,
            "context": context,
            "metadata": dict(metadata or {}),
        }

        if execution_id is not None:
            arguments["execution_id"] = execution_id

        execution = WorkflowExecution(**arguments)

        self._persist(execution)
        self._increment_metric(
            "workflow.created"
        )

        structured_log(
            self.logger,
            event="workflow.created",
            execution_id=execution.execution_id,
            workflow_id=execution.definition.workflow_id,
            status=execution.status.value,
        )

        return execution

    def load_execution(
        self,
        execution_id: str,
    ) -> WorkflowExecution:
        """Load a persisted workflow execution."""
        if self.repository is None:
            raise RuntimeError(
                "WorkflowEngine requires a repository "
                "to load persisted executions."
            )

        execution = self.repository.get(
            execution_id
        )

        if execution is None:
            raise KeyError(
                f"Unknown workflow execution: "
                f"'{execution_id}'."
            )

        return execution

    def start(
        self,
        execution: WorkflowExecution,
    ) -> WorkflowExecution:
        """Start a pending workflow execution."""
        self.validator.validate_can_start(execution)
        execution.start()

        self._persist(execution)
        self._increment_metric(
            "workflow.started"
        )

        structured_log(
            self.logger,
            event="workflow.started",
            execution_id=execution.execution_id,
            workflow_id=execution.definition.workflow_id,
            status=execution.status.value,
        )

        return execution

    def get_next_step(
        self,
        execution: WorkflowExecution,
    ) -> WorkflowStep | None:
        """Return the next pending step without starting it."""
        return self.navigator.get_next_step(execution)

    def start_next_step(
        self,
        execution: WorkflowExecution,
    ) -> WorkflowStep | None:
        """Select and start the next pending step."""
        step = self.navigator.get_next_step(execution)

        if step is None:
            return None

        execution.select_step(step.step_id)
        step.start()

        self._persist(execution)

        return step

    def complete_current_step(
        self,
        execution: WorkflowExecution,
        *,
        output: Any = None,
    ) -> WorkflowStep:
        """Complete the currently selected running step."""
        step = execution.current_step

        if step is None:
            raise RuntimeError(
                "No current workflow step is selected."
            )

        step.complete(output)
        execution.context.set_output(
            step.step_id,
            output,
        )
        execution.current_step_id = None

        self._persist(execution)

        return step

    def fail_current_step(
        self,
        execution: WorkflowExecution,
        *,
        error: str,
        fail_workflow: bool = True,
    ) -> WorkflowStep:
        """Fail the current step and optionally the workflow."""
        step = execution.current_step

        if step is None:
            raise RuntimeError(
                "No current workflow step is selected."
            )

        step.fail(error)
        execution.current_step_id = None

        if fail_workflow:
            execution.fail(error)

        self._persist(execution)

        if fail_workflow:
            self._increment_metric(
                "workflow.failed"
            )

        return step

    def complete(
        self,
        execution: WorkflowExecution,
    ) -> WorkflowExecution:
        """Complete a workflow whose steps are all terminal."""
        self.validator.validate_can_complete(execution)
        execution.complete()

        self._persist(execution)
        self._increment_metric(
            "workflow.completed"
        )

        structured_log(
            self.logger,
            event="workflow.completed",
            execution_id=execution.execution_id,
            workflow_id=execution.definition.workflow_id,
            status=execution.status.value,
        )

        return execution

    def fail(
        self,
        execution: WorkflowExecution,
        *,
        error: str,
    ) -> WorkflowExecution:
        """Fail a running workflow execution."""
        execution.fail(error)

        self._persist(execution)
        self._increment_metric(
            "workflow.failed"
        )

        structured_log(
            self.logger,
            event="workflow.failed",
            execution_id=execution.execution_id,
            workflow_id=execution.definition.workflow_id,
            status=execution.status.value,
            error=error,
        )

        return execution

    def cancel(
        self,
        execution: WorkflowExecution,
    ) -> WorkflowExecution:
        """Cancel a pending or running workflow execution."""
        execution.cancel()

        self._persist(execution)

        return execution

    def _increment_metric(
        self,
        name: str,
    ) -> None:
        """Increment an observability counter when configured."""
        if self.metrics is not None:
            self.metrics.increment(name)

    def _persist(
        self,
        execution: WorkflowExecution,
    ) -> None:
        """Persist execution state when a repository is configured."""
        if self.repository is not None:
            self.repository.save(execution)
