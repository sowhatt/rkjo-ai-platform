"""Mutable execution context shared by workflow steps."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(slots=True)
class WorkflowContext:
    """Data transported and enriched during workflow execution."""

    input_data: dict[str, Any] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """Read a value using variables first, then input data."""
        if key in self.variables:
            return self.variables[key]

        return self.input_data.get(key, default)

    def set_variable(
        self,
        key: str,
        value: Any,
    ) -> None:
        """Store or replace a workflow variable."""
        if not key or not key.strip():
            raise ValueError(
                "Workflow variable key must not be empty."
            )

        self.variables[key] = value

    def set_output(
        self,
        step_id: str,
        value: Any,
    ) -> None:
        """Store the output produced by a workflow step."""
        if not step_id or not step_id.strip():
            raise ValueError(
                "Workflow step identifier must not be empty."
            )

        self.outputs[step_id] = value

    def update_variables(
        self,
        values: Mapping[str, Any],
    ) -> None:
        """Merge several values into the workflow variables."""
        self.variables.update(values)

    def snapshot(self) -> dict[str, Any]:
        """Return an isolated serializable-style snapshot."""
        return {
            "input_data": deepcopy(self.input_data),
            "variables": deepcopy(self.variables),
            "outputs": deepcopy(self.outputs),
            "metadata": deepcopy(self.metadata),
        }
