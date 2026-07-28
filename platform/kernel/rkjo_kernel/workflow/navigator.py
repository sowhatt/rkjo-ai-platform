"""Navigation services for sequential workflow execution."""

from rkjo_kernel.workflow.models.step_status import StepStatus
from rkjo_kernel.workflow.models.workflow_execution import (
    WorkflowExecution,
)
from rkjo_kernel.workflow.models.workflow_status import (
    WorkflowStatus,
)
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep


class WorkflowNavigator:
    """Locate the next step of a sequential workflow."""

    def get_next_step(
        self,
        execution: WorkflowExecution,
    ) -> WorkflowStep | None:
        """Return the first pending step in workflow order."""
        if execution.status != WorkflowStatus.RUNNING:
            return None

        return next(
            (
                step
                for step in execution.definition.ordered_steps()
                if step.status == StepStatus.PENDING
            ),
            None,
        )

    def has_next_step(
        self,
        execution: WorkflowExecution,
    ) -> bool:
        """Return whether a pending step remains."""
        return self.get_next_step(execution) is not None

    def get_previous_step(
        self,
        execution: WorkflowExecution,
        step_id: str,
    ) -> WorkflowStep | None:
        """Return the step immediately preceding a given step."""
        ordered_steps = execution.definition.ordered_steps()

        for index, step in enumerate(ordered_steps):
            if step.step_id != step_id:
                continue

            if index == 0:
                return None

            return ordered_steps[index - 1]

        raise KeyError(
            f"Unknown workflow step: '{step_id}'."
        )
