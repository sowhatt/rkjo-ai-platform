"""Execute capability-targeted workflow steps through authorized tools."""

from __future__ import annotations

from copy import deepcopy

from rkjo_kernel.registry.discovery import (
    AgentDiscovery,
    DiscoveryCriteria,
)
from rkjo_kernel.tools.context import ToolExecutionContext
from rkjo_kernel.tools.invoker import ToolInvoker
from rkjo_kernel.tools.resolver import CapabilityToolResolver
from rkjo_kernel.workflow.agent_execution_adapter import (
    AgentExecutionAdapter,
)
from rkjo_kernel.workflow.execution_result import ExecutionResult
from rkjo_kernel.workflow.models.workflow_context import WorkflowContext
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep


class CapabilityToolExecutionAdapter(AgentExecutionAdapter):
    """Discover a capability and execute one of its declared tools.

    The adapter deliberately does not replace AgentRuntime. It is a
    synchronous workflow bridge for capability-aware tool execution.
    """

    def __init__(
        self,
        *,
        discovery: AgentDiscovery,
        resolver: CapabilityToolResolver,
        invoker: ToolInvoker,
    ) -> None:
        self.discovery = discovery
        self.resolver = resolver
        self.invoker = invoker

    def execute(
        self,
        *,
        step: WorkflowStep,
        context: WorkflowContext,
    ) -> ExecutionResult:
        capability_name = step.capability_name

        if capability_name is None:
            return ExecutionResult.failed(
                error=(
                    "CapabilityToolExecutionAdapter requires a "
                    "workflow step targeted by capability_name."
                ),
                metadata={
                    "adapter": "capability_tool",
                    "workflow_step_id": step.step_id,
                },
            )

        discovery_result = self.discovery.discover(
            DiscoveryCriteria(capability_name=capability_name)
        )

        if discovery_result is None:
            return ExecutionResult.failed(
                error=(
                    "No available agent provides capability "
                    f"'{capability_name}'."
                ),
                metadata={
                    "adapter": "capability_tool",
                    "capability_name": capability_name,
                    "workflow_step_id": step.step_id,
                },
            )

        try:
            resolved_tools = self.resolver.resolve(discovery_result)
        except Exception as exc:
            return ExecutionResult.failed(
                error=f"{exc.__class__.__name__}: {exc}",
                metadata={
                    "adapter": "capability_tool",
                    "capability_name": capability_name,
                    "workflow_step_id": step.step_id,
                    "exception_type": exc.__class__.__name__,
                },
            )

        tool_name = self._select_tool_name(
            step=step,
            resolved_tool_names=[tool.name for tool in resolved_tools],
        )

        if tool_name is None:
            return ExecutionResult.failed(
                error=(
                    "Workflow step must define metadata['tool_name'] "
                    "when the selected capability exposes zero or "
                    "multiple tools."
                ),
                metadata={
                    "adapter": "capability_tool",
                    "capability_name": capability_name,
                    "workflow_step_id": step.step_id,
                    "resolved_tools": [
                        tool.name for tool in resolved_tools
                    ],
                },
            )

        tenant_id = context.metadata.get("tenant_id")

        if not isinstance(tenant_id, str) or not tenant_id.strip():
            return ExecutionResult.failed(
                error=(
                    "Capability tool execution requires "
                    "context.metadata['tenant_id']."
                ),
                metadata={
                    "adapter": "capability_tool",
                    "capability_name": capability_name,
                    "workflow_step_id": step.step_id,
                    "tool_name": tool_name,
                },
            )

        tool_context = ToolExecutionContext(
            tenant_id=tenant_id,
            agent_name=discovery_result.agent.name,
            capability_name=discovery_result.capability.name,
            workflow_execution_id=self._optional_metadata_string(
                context,
                "workflow_execution_id",
            ),
            workflow_step_id=step.step_id,
            correlation_id=self._optional_metadata_string(
                context,
                "correlation_id",
            ),
            metadata={
                **deepcopy(context.metadata),
                **deepcopy(step.metadata),
            },
        )

        payload = deepcopy(context.input_data)
        payload.update(deepcopy(context.variables))

        if context.outputs:
            payload["workflow_outputs"] = deepcopy(context.outputs)

        result = self.invoker.invoke_authorized(
            capability=discovery_result.capability,
            tool_name=tool_name,
            payload=payload,
            context=tool_context,
        )

        metadata = {
            "adapter": "capability_tool",
            "routing_mode": "capability",
            "capability_name": capability_name,
            "selected_agent_name": discovery_result.agent.name,
            "selected_capability_version": (
                discovery_result.capability.version
            ),
            "discovery_score": discovery_result.score,
            "workflow_step_id": step.step_id,
            "tool_name": tool_name,
            "tenant_id": tool_context.tenant_id,
        }

        if result.success:
            return ExecutionResult.succeeded(
                output=result.output,
                metadata=metadata,
            )

        return ExecutionResult.failed(
            error=result.error or "Tool execution failed.",
            metadata=metadata,
        )

    @staticmethod
    def _select_tool_name(
        *,
        step: WorkflowStep,
        resolved_tool_names: list[str],
    ) -> str | None:
        configured = step.metadata.get("tool_name")

        if isinstance(configured, str) and configured.strip():
            return configured.strip().lower()

        if len(resolved_tool_names) == 1:
            return resolved_tool_names[0]

        return None

    @staticmethod
    def _optional_metadata_string(
        context: WorkflowContext,
        key: str,
    ) -> str | None:
        value = context.metadata.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

        return None
