"""Transverse execution context propagated across RKJO runtimes."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, MutableMapping
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Technical and governance context for one execution path.

    WorkflowContext carries mutable business data between workflow steps.
    ExecutionContext carries stable correlation and governance identifiers.
    """

    mission_id: str
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    workflow_execution_id: str | None = None
    step_id: str | None = None
    agent_id: str | None = None
    capability_name: str | None = None
    tool_call_id: str | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    correlation_id: str | None = None
    request_id: str | None = None
    parent_span_id: str | None = None
    policy_context: dict[str, Any] = field(default_factory=dict)
    budget: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.mission_id or not self.mission_id.strip():
            raise ValueError("ExecutionContext mission_id must not be empty.")
        if not self.trace_id or not self.trace_id.strip():
            raise ValueError("ExecutionContext trace_id must not be empty.")

    def for_workflow(self, workflow_execution_id: str) -> "ExecutionContext":
        """Return a derived context bound to one workflow execution."""
        return replace(
            self,
            workflow_execution_id=self._required(
                workflow_execution_id,
                "workflow_execution_id",
            ),
        )

    def for_step(self, step_id: str) -> "ExecutionContext":
        """Return a derived context bound to one workflow step."""
        return replace(
            self,
            step_id=self._required(step_id, "step_id"),
        )

    def for_agent(
        self,
        agent_id: str,
        capability_name: str | None = None,
    ) -> "ExecutionContext":
        """Return a derived context bound to one agent/capability."""
        normalized_capability = (
            capability_name.strip().lower()
            if capability_name is not None
            else None
        )
        if capability_name is not None and not normalized_capability:
            raise ValueError("capability_name must not be empty.")

        return replace(
            self,
            agent_id=self._required(agent_id, "agent_id"),
            capability_name=normalized_capability,
        )

    def for_tool_call(self, tool_call_id: str) -> "ExecutionContext":
        """Return a derived context bound to one tool invocation."""
        return replace(
            self,
            tool_call_id=self._required(tool_call_id, "tool_call_id"),
        )

    def as_metadata(self) -> dict[str, Any]:
        """Serialize non-null context fields for messages and structured logs."""
        values: dict[str, Any] = {
            "trace_id": self.trace_id,
            "mission_id": self.mission_id,
            "workflow_execution_id": self.workflow_execution_id,
            "workflow_step_id": self.step_id,
            "agent_id": self.agent_id,
            "capability_name": self.capability_name,
            "tool_call_id": self.tool_call_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "correlation_id": self.correlation_id,
            "request_id": self.request_id,
            "parent_span_id": self.parent_span_id,
            "policy_context": self.policy_context or None,
            "budget": self.budget or None,
        }
        values.update(self.metadata)
        return {key: value for key, value in values.items() if value is not None}

    def inject_into(self, metadata: MutableMapping[str, Any]) -> None:
        """Merge the execution context into an existing metadata mapping."""
        metadata.update(self.as_metadata())

    @staticmethod
    def _required(value: str, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{field_name} must not be empty.")
        return normalized
