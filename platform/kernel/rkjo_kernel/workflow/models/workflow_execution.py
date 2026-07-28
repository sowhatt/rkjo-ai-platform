"""Runtime state of a workflow execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from rkjo_kernel.workflow.exceptions import (
    InvalidWorkflowTransitionError,
)
from rkjo_kernel.workflow.models.step_status import StepStatus
from rkjo_kernel.workflow.models.workflow_context import (
    WorkflowContext,
)
from rkjo_kernel.workflow.models.workflow_definition import (
    WorkflowDefinition,
)
from rkjo_kernel.workflow.models.workflow_status import WorkflowStatus
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class WorkflowExecution:
    """State associated with one execution of a workflow."""

    definition: WorkflowDefinition
    context: WorkflowContext = field(
        default_factory=WorkflowContext
    )
    execution_id: str = field(
        default_factory=lambda: str(uuid4())
    )
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_step_id: str | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate execution identity."""
        if not self.execution_id or not self.execution_id.strip():
            raise ValueError(
                "Workflow execution_id must not be empty."
            )

    @property
    def is_terminal(self) -> bool:
        """Return whether the execution is finished."""
        return self.status.is_terminal

    @property
    def current_step(self) -> WorkflowStep | None:
        """Return the currently selected workflow step."""
        if self.current_step_id is None:
            return None

        return self.definition.get_step(
            self.current_step_id
        )

    def start(self) -> None:
        """Start a pending workflow execution."""
        self._ensure_transition(
            allowed={WorkflowStatus.PENDING},
            target=WorkflowStatus.RUNNING,
        )

        self.status = WorkflowStatus.RUNNING
        self.started_at = utc_now()
        self.completed_at = None
        self.error = None

    def select_step(
        self,
        step_id: str,
    ) -> WorkflowStep:
        """Select a pending step as the current execution step."""
        if self.status != WorkflowStatus.RUNNING:
            raise InvalidWorkflowTransitionError(
                "A workflow step can only be selected while "
                "the workflow is running."
            )

        step = self.definition.get_step(step_id)

        if step is None:
            raise KeyError(
                f"Unknown workflow step: '{step_id}'."
            )

        if step.status != StepStatus.PENDING:
            raise InvalidWorkflowTransitionError(
                f"Workflow step '{step_id}' cannot be selected "
                f"from status '{step.status.value}'."
            )

        self.current_step_id = step_id
        return step

    def complete(self) -> None:
        """Complete a running workflow."""
        self._ensure_transition(
            allowed={WorkflowStatus.RUNNING},
            target=WorkflowStatus.COMPLETED,
        )

        unfinished_steps = [
            step.step_id
            for step in self.definition.steps
            if not step.status.is_terminal
        ]

        if unfinished_steps:
            raise InvalidWorkflowTransitionError(
                "Cannot complete workflow while steps remain "
                f"unfinished: {unfinished_steps}."
            )

        failed_steps = [
            step.step_id
            for step in self.definition.steps
            if step.status == StepStatus.FAILED
        ]

        if failed_steps:
            raise InvalidWorkflowTransitionError(
                "Cannot complete workflow containing failed "
                f"steps: {failed_steps}."
            )

        self.status = WorkflowStatus.COMPLETED
        self.current_step_id = None
        self.error = None
        self.completed_at = utc_now()

    def fail(self, error: str) -> None:
        """Fail a running workflow execution."""
        if not error or not error.strip():
            raise ValueError(
                "A failed workflow requires an error message."
            )

        self._ensure_transition(
            allowed={WorkflowStatus.RUNNING},
            target=WorkflowStatus.FAILED,
        )

        self.status = WorkflowStatus.FAILED
        self.error = error
        self.completed_at = utc_now()

    def cancel(self) -> None:
        """Cancel a pending or running workflow execution."""
        self._ensure_transition(
            allowed={
                WorkflowStatus.PENDING,
                WorkflowStatus.RUNNING,
            },
            target=WorkflowStatus.CANCELLED,
        )

        self.status = WorkflowStatus.CANCELLED
        self.completed_at = utc_now()

    def progress(self) -> float:
        """Return completion progress as a value from 0.0 to 1.0."""
        total = len(self.definition.steps)

        if total == 0:
            return 1.0 if self.status.is_terminal else 0.0

        finished = sum(
            1
            for step in self.definition.steps
            if step.status.is_terminal
        )

        return finished / total

    def _ensure_transition(
        self,
        *,
        allowed: set[WorkflowStatus],
        target: WorkflowStatus,
    ) -> None:
        """Check whether the requested transition is valid."""
        if self.status not in allowed:
            raise InvalidWorkflowTransitionError(
                f"Cannot move workflow execution "
                f"'{self.execution_id}' from "
                f"'{self.status.value}' to '{target.value}'."
            )
