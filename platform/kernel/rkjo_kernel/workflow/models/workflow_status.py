"""Workflow lifecycle statuses."""

from enum import StrEnum


class WorkflowStatus(StrEnum):
    """Possible states of a workflow execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        """Return whether the workflow can no longer continue."""
        return self in {
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
        }
