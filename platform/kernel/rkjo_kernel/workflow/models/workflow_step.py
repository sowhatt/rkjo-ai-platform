"""Definition and runtime state of a workflow step."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from rkjo_kernel.workflow.exceptions import (
    InvalidStepTransitionError,
)
from rkjo_kernel.workflow.models.step_status import StepStatus


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class WorkflowStep:
    """One ordered unit of work inside a workflow."""

    step_id: str
    name: str
    agent_name: str | None = None
    capability_name: str | None = None
    description: str | None = None
    position: int = 0
    input_mapping: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    status: StepStatus = StepStatus.PENDING
    output: Any = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate the static step definition."""
        if not self.step_id or not self.step_id.strip():
            raise ValueError(
                "Workflow step_id must not be empty."
            )

        if not self.name or not self.name.strip():
            raise ValueError(
                "Workflow step name must not be empty."
            )

        if self.agent_name is not None:
            if (
                not isinstance(self.agent_name, str)
                or not self.agent_name.strip()
            ):
                raise ValueError(
                    "Workflow step agent_name must be a "
                    "non-empty string when provided."
                )

            self.agent_name = self.agent_name.strip()

        if self.capability_name is not None:
            if (
                not isinstance(self.capability_name, str)
                or not self.capability_name.strip()
            ):
                raise ValueError(
                    "Workflow step capability_name must be a "
                    "non-empty string when provided."
                )

            self.capability_name = (
                self.capability_name.strip()
            )

        has_agent_target = self.agent_name is not None
        has_capability_target = (
            self.capability_name is not None
        )

        if has_agent_target == has_capability_target:
            raise ValueError(
                "Workflow step must define exactly one "
                "routing target: agent_name or "
                "capability_name."
            )

        if self.position < 0:
            raise ValueError(
                "Workflow step position must be greater than "
                "or equal to zero."
            )

    @property
    def routing_mode(self) -> str:
        """Return the routing strategy used by the step."""
        if self.agent_name is not None:
            return "agent"

        return "capability"

    @property
    def routing_target(self) -> str:
        """Return the configured routing target."""
        if self.agent_name is not None:
            return self.agent_name

        if self.capability_name is not None:
            return self.capability_name

        raise RuntimeError(
            "Workflow step has no routing target."
        )

    def start(self) -> None:
        """Move the step from PENDING to RUNNING."""
        self._ensure_transition(
            allowed={StepStatus.PENDING},
            target=StepStatus.RUNNING,
        )

        self.status = StepStatus.RUNNING
        self.started_at = utc_now()
        self.completed_at = None
        self.output = None
        self.error = None

    def complete(self, output: Any = None) -> None:
        """Complete a running step and store its output."""
        self._ensure_transition(
            allowed={StepStatus.RUNNING},
            target=StepStatus.COMPLETED,
        )

        self.status = StepStatus.COMPLETED
        self.output = output
        self.error = None
        self.completed_at = utc_now()

    def fail(self, error: str) -> None:
        """Mark a running step as failed."""
        if not error or not error.strip():
            raise ValueError(
                "A failed workflow step requires an error message."
            )

        self._ensure_transition(
            allowed={StepStatus.RUNNING},
            target=StepStatus.FAILED,
        )

        self.status = StepStatus.FAILED
        self.error = error
        self.completed_at = utc_now()

    def skip(self) -> None:
        """Skip a step that has not started."""
        self._ensure_transition(
            allowed={StepStatus.PENDING},
            target=StepStatus.SKIPPED,
        )

        self.status = StepStatus.SKIPPED
        self.completed_at = utc_now()

    def reset(self) -> None:
        """Reset a terminal step for a future retry."""
        self._ensure_transition(
            allowed={
                StepStatus.COMPLETED,
                StepStatus.FAILED,
                StepStatus.SKIPPED,
            },
            target=StepStatus.PENDING,
        )

        self.status = StepStatus.PENDING
        self.output = None
        self.error = None
        self.started_at = None
        self.completed_at = None

    def _ensure_transition(
        self,
        *,
        allowed: set[StepStatus],
        target: StepStatus,
    ) -> None:
        """Check whether the requested status transition is valid."""
        if self.status not in allowed:
            raise InvalidStepTransitionError(
                f"Cannot move workflow step '{self.step_id}' "
                f"from '{self.status.value}' to '{target.value}'."
            )
