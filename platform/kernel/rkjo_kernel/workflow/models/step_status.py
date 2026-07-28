"""Workflow step lifecycle statuses."""

from enum import StrEnum


class StepStatus(StrEnum):
    """Possible states of a workflow step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

    @property
    def is_terminal(self) -> bool:
        """Return whether the step can no longer continue."""
        return self in {
            StepStatus.COMPLETED,
            StepStatus.FAILED,
            StepStatus.SKIPPED,
        }
