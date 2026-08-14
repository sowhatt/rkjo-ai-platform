"""Execute capability-targeted workflow steps through local runtimes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from rkjo_kernel.registry.discovery import (
    AgentDiscovery,
    DiscoveryCriteria,
)
from rkjo_kernel.runtime.agent_runtime import AgentRuntime
from rkjo_kernel.workflow.agent_execution_adapter import (
    AgentExecutionAdapter,
)
from rkjo_kernel.workflow.execution_result import ExecutionResult
from rkjo_kernel.workflow.models.workflow_context import (
    WorkflowContext,
)
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep
from rkjo_kernel.workflow.runtime_execution_adapter import (
    RuntimeExecutionAdapter,
)


class CapabilityRuntimeExecutionAdapter(
    AgentExecutionAdapter
):
    """Discover and execute the best local agent for a capability.

    This adapter provides a synchronous bridge between:

    - capability-based workflow routing;
    - AgentDiscovery;
    - local AgentRuntime instances.

    Distributed RabbitMQ request/reply execution will use a
    separate adapter.
    """

    def __init__(
        self,
        *,
        discovery: AgentDiscovery,
        runtimes: Mapping[str, AgentRuntime],
        source: str = "rkjo.workflow",
        priority: int = 5,
    ) -> None:
        self.discovery = discovery
        self.runtime_adapter = RuntimeExecutionAdapter(
            runtimes=runtimes,
            source=source,
            priority=priority,
        )

    def execute(
        self,
        *,
        step: WorkflowStep,
        context: WorkflowContext,
    ) -> ExecutionResult:
        """Discover and execute an agent for the step capability."""
        capability_name = step.capability_name

        if capability_name is None:
            return ExecutionResult.failed(
                error=(
                    "CapabilityRuntimeExecutionAdapter requires "
                    "a workflow step targeted by "
                    "capability_name."
                ),
                metadata={
                    "adapter": "capability_runtime",
                    "routing_mode": step.routing_mode,
                    "agent_name": step.agent_name,
                    "workflow_step_id": step.step_id,
                },
            )

        try:
            discovery_result = self.discovery.discover(
                DiscoveryCriteria(
                    capability_name=capability_name,
                )
            )
        except Exception as exc:
            message = (
                str(exc).strip()
                or exc.__class__.__name__
            )

            return ExecutionResult.failed(
                error=(
                    "Agent discovery failed for capability "
                    f"'{capability_name}': "
                    f"{exc.__class__.__name__}: {message}"
                ),
                metadata={
                    "adapter": "capability_runtime",
                    "routing_mode": "capability",
                    "capability_name": capability_name,
                    "workflow_step_id": step.step_id,
                    "exception_type": (
                        exc.__class__.__name__
                    ),
                },
            )

        if discovery_result is None:
            return ExecutionResult.failed(
                error=(
                    "No available agent provides capability "
                    f"'{capability_name}'."
                ),
                metadata={
                    "adapter": "capability_runtime",
                    "routing_mode": "capability",
                    "capability_name": capability_name,
                    "workflow_step_id": step.step_id,
                },
            )

        selected_agent = discovery_result.agent

        resolved_step = replace(
            step,
            agent_name=selected_agent.name,
            capability_name=None,
        )

        result = self.runtime_adapter.execute(
            step=resolved_step,
            context=context,
        )

        metadata = {
            **result.metadata,
            "adapter": "capability_runtime",
            "routing_mode": "capability",
            "capability_name": capability_name,
            "selected_agent_name": selected_agent.name,
            "selected_agent_version": (
                selected_agent.version
            ),
            "selected_capability_version": (
                discovery_result.capability.version
            ),
            "discovery_score": discovery_result.score,
        }

        return ExecutionResult(
            success=result.success,
            output=result.output,
            error=result.error,
            metadata=metadata,
            duration_ms=result.duration_ms,
        )

    def register_runtime(
        self,
        runtime: AgentRuntime,
    ) -> None:
        """Register or replace a local runtime."""
        self.runtime_adapter.register_runtime(runtime)

    def unregister_runtime(
        self,
        agent_name: str,
    ) -> AgentRuntime | None:
        """Remove and return a local runtime."""
        return self.runtime_adapter.unregister_runtime(
            agent_name
        )

    def get_runtime(
        self,
        agent_name: str,
    ) -> AgentRuntime | None:
        """Return a local runtime by agent name."""
        return self.runtime_adapter.get_runtime(agent_name)
