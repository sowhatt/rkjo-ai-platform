"""Validation services for workflow definitions and executions."""

from rkjo_kernel.workflow.exceptions import (
    InvalidWorkflowDefinitionError,
    InvalidWorkflowTransitionError,
)
from rkjo_kernel.workflow.models.step_status import StepStatus
from rkjo_kernel.workflow.models.workflow_definition import (
    WorkflowDefinition,
)
from rkjo_kernel.workflow.models.workflow_execution import (
    WorkflowExecution,
)
from rkjo_kernel.workflow.models.workflow_status import (
    WorkflowStatus,
)


class WorkflowValidator:
    """Validate workflow definitions and execution invariants."""

    def validate_definition(
        self,
        definition: WorkflowDefinition,
    ) -> None:
        """Ensure a workflow definition can be executed."""
        if not definition.steps:
            raise InvalidWorkflowDefinitionError(
                "A workflow definition must contain at least one step."
            )

        expected_positions = list(
            range(len(definition.steps))
        )
        actual_positions = [
            step.position
            for step in definition.ordered_steps()
        ]

        if actual_positions != expected_positions:
            raise InvalidWorkflowDefinitionError(
                "Workflow step positions must be contiguous and "
                "start at zero."
            )

    def validate_can_start(
        self,
        execution: WorkflowExecution,
    ) -> None:
        """Ensure an execution can transition to RUNNING."""
        if execution.status != WorkflowStatus.PENDING:
            raise InvalidWorkflowTransitionError(
                "Only a pending workflow execution can be started."
            )

        self.validate_definition(execution.definition)

        non_pending_steps = [
            step.step_id
            for step in execution.definition.steps
            if step.status != StepStatus.PENDING
        ]

        if non_pending_steps:
            raise InvalidWorkflowTransitionError(
                "A workflow cannot start with non-pending steps: "
                f"{non_pending_steps}."
            )

    def validate_can_complete(
        self,
        execution: WorkflowExecution,
    ) -> None:
        """Ensure an execution can transition to COMPLETED."""
        if execution.status != WorkflowStatus.RUNNING:
            raise InvalidWorkflowTransitionError(
                "Only a running workflow execution can be completed."
            )

        failed_steps = [
            step.step_id
            for step in execution.definition.steps
            if step.status == StepStatus.FAILED
        ]

        if failed_steps:
            raise InvalidWorkflowTransitionError(
                "A workflow containing failed steps cannot complete: "
                f"{failed_steps}."
            )

        unfinished_steps = [
            step.step_id
            for step in execution.definition.steps
            if not step.status.is_terminal
        ]

        if unfinished_steps:
            raise InvalidWorkflowTransitionError(
                "A workflow containing unfinished steps cannot "
                f"complete: {unfinished_steps}."
            )
