"""Static workflow definition."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from rkjo_kernel.workflow.exceptions import (
    InvalidWorkflowDefinitionError,
)
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep


@dataclass(slots=True)
class WorkflowDefinition:
    """Ordered and versioned description of a workflow."""

    workflow_id: str
    name: str
    version: str = "1.0.0"
    description: str | None = None
    steps: list[WorkflowStep] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and normalize the workflow definition."""
        if not self.workflow_id or not self.workflow_id.strip():
            raise InvalidWorkflowDefinitionError(
                "Workflow workflow_id must not be empty."
            )

        if not self.name or not self.name.strip():
            raise InvalidWorkflowDefinitionError(
                "Workflow name must not be empty."
            )

        if not self.version or not self.version.strip():
            raise InvalidWorkflowDefinitionError(
                "Workflow version must not be empty."
            )

        self._validate_steps()
        self.steps.sort(key=lambda step: step.position)

    def add_step(self, step: WorkflowStep) -> None:
        """Add a step while preserving definition invariants."""
        if self.get_step(step.step_id) is not None:
            raise InvalidWorkflowDefinitionError(
                f"Duplicate workflow step_id: '{step.step_id}'."
            )

        if any(
            existing.position == step.position
            for existing in self.steps
        ):
            raise InvalidWorkflowDefinitionError(
                f"Duplicate workflow step position: "
                f"{step.position}."
            )

        self.steps.append(step)
        self.steps.sort(key=lambda item: item.position)

    def get_step(
        self,
        step_id: str,
    ) -> WorkflowStep | None:
        """Return a step by identifier."""
        return next(
            (
                step
                for step in self.steps
                if step.step_id == step_id
            ),
            None,
        )

    def ordered_steps(self) -> tuple[WorkflowStep, ...]:
        """Return workflow steps in execution order."""
        return tuple(
            sorted(
                self.steps,
                key=lambda step: step.position,
            )
        )

    def _validate_steps(self) -> None:
        """Ensure step identifiers and positions are unique."""
        self._ensure_unique(
            values=(step.step_id for step in self.steps),
            label="step_id",
        )
        self._ensure_unique(
            values=(step.position for step in self.steps),
            label="step position",
        )

    @staticmethod
    def _ensure_unique(
        *,
        values: Iterable[object],
        label: str,
    ) -> None:
        """Ensure all supplied values are unique."""
        seen: set[object] = set()

        for value in values:
            if value in seen:
                raise InvalidWorkflowDefinitionError(
                    f"Duplicate workflow {label}: '{value}'."
                )

            seen.add(value)
