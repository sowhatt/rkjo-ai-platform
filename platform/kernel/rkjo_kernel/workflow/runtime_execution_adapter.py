"""Synchronous adapter executing workflow steps through local runtimes."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.runtime.agent_runtime import AgentRuntime
from rkjo_kernel.workflow.agent_execution_adapter import (
    AgentExecutionAdapter,
)
from rkjo_kernel.workflow.execution_result import ExecutionResult
from rkjo_kernel.workflow.models.workflow_context import WorkflowContext
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep


class RuntimeExecutionAdapter(AgentExecutionAdapter):
    """Execute agents synchronously through local AgentRuntime instances.

    This adapter is intended for:

    - local development;
    - unit and integration tests;
    - single-process execution;
    - validating the complete workflow-to-agent chain.

    Distributed execution through RabbitMQ will use another adapter.
    """

    def __init__(
        self,
        *,
        runtimes: Mapping[str, AgentRuntime],
        source: str = "rkjo.workflow",
        priority: int = 5,
    ) -> None:
        if not source or not source.strip():
            raise ValueError(
                "Runtime execution source must not be empty."
            )

        if priority < 1 or priority > 10:
            raise ValueError(
                "Runtime execution priority must be between 1 and 10."
            )

        self._runtimes = dict(runtimes)
        self.source = source
        self.priority = priority

    def execute(
        self,
        *,
        step: WorkflowStep,
        context: WorkflowContext,
    ) -> ExecutionResult:
        """Execute the agent referenced by a workflow step."""
        if step.agent_name is None:
            return ExecutionResult.failed(
                error=(
                    "RuntimeExecutionAdapter requires a "
                    "workflow step targeted by agent_name. "
                    "Capability "
                    f"'{step.capability_name}' must be "
                    "resolved before local execution."
                ),
                metadata={
                    "adapter": "runtime",
                    "capability_name": (
                        step.capability_name
                    ),
                    "workflow_step_id": step.step_id,
                },
            )

        runtime = self._runtimes.get(step.agent_name)

        if runtime is None:
            return ExecutionResult.failed(
                error=(
                    "No local runtime is registered for agent "
                    f"'{step.agent_name}'."
                ),
                metadata={
                    "adapter": "runtime",
                    "agent_name": step.agent_name,
                    "workflow_step_id": step.step_id,
                },
            )

        actual_agent_name = runtime.agent.agent_name

        if actual_agent_name != step.agent_name:
            return ExecutionResult.failed(
                error=(
                    f"Runtime registered as '{step.agent_name}' "
                    f"contains agent '{actual_agent_name}'."
                ),
                metadata={
                    "adapter": "runtime",
                    "expected_agent_name": step.agent_name,
                    "actual_agent_name": actual_agent_name,
                    "workflow_step_id": step.step_id,
                },
            )

        message = self._build_message(
            step=step,
            context=context,
        )

        try:
            output = runtime.execute(message)
        except Exception as exc:
            error_message = (
                str(exc).strip()
                or exc.__class__.__name__
            )

            return ExecutionResult.failed(
                error=(
                    f"{exc.__class__.__name__}: "
                    f"{error_message}"
                ),
                duration_ms=runtime.last_duration_ms,
                metadata=self._build_result_metadata(
                    runtime=runtime,
                    step=step,
                    message=message,
                    extra={
                        "exception_type": (
                            exc.__class__.__name__
                        ),
                    },
                ),
            )

        return ExecutionResult.succeeded(
            output=output,
            duration_ms=runtime.last_duration_ms,
            metadata=self._build_result_metadata(
                runtime=runtime,
                step=step,
                message=message,
            ),
        )

    def register_runtime(
        self,
        runtime: AgentRuntime,
    ) -> None:
        """Register or replace a local agent runtime."""
        self._runtimes[
            runtime.agent.agent_name
        ] = runtime

    def unregister_runtime(
        self,
        agent_name: str,
    ) -> AgentRuntime | None:
        """Remove and return a local runtime when present."""
        return self._runtimes.pop(
            agent_name,
            None,
        )

    def get_runtime(
        self,
        agent_name: str,
    ) -> AgentRuntime | None:
        """Return the runtime registered for an agent."""
        return self._runtimes.get(agent_name)

    def _build_message(
        self,
        *,
        step: WorkflowStep,
        context: WorkflowContext,
    ) -> AgentMessage:
        """Create the AgentMessage sent to the local runtime."""
        payload: dict[str, Any] = deepcopy(
            context.input_data
        )

        payload.update(
            deepcopy(context.variables)
        )

        if context.outputs:
            payload["workflow_outputs"] = deepcopy(
                context.outputs
            )

        message_metadata = {
            **deepcopy(context.metadata),
            **deepcopy(step.metadata),
            "workflow_step_id": step.step_id,
            "workflow_step_name": step.name,
            "execution_adapter": "runtime",
        }

        arguments: dict[str, Any] = {
            "source": self.source,
            "target": step.agent_name,
            "message_type": "mission",
            "priority": self.priority,
            "payload": payload,
            "metadata": message_metadata,
        }

        correlation_id = context.metadata.get(
            "correlation_id"
        )

        if (
            isinstance(correlation_id, str)
            and correlation_id.strip()
        ):
            arguments["correlation_id"] = (
                correlation_id
            )

        return AgentMessage(**arguments)

    @staticmethod
    def _build_result_metadata(
        *,
        runtime: AgentRuntime,
        step: WorkflowStep,
        message: AgentMessage,
        extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build technical trace metadata for an execution result."""
        metadata = {
            "adapter": "runtime",
            "agent_name": runtime.agent.agent_name,
            "queue_name": runtime.agent.queue_name,
            "workflow_step_id": step.step_id,
            "message_id": message.message_id,
            "correlation_id": message.correlation_id,
            "runtime_status": runtime.status.value,
        }

        metadata.update(
            dict(extra or {})
        )

        return metadata
