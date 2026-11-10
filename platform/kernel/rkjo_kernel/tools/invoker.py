from dataclasses import dataclass
from typing import Any

from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.tools.approval import ToolApprovalService
from rkjo_kernel.tools.context import ToolExecutionContext
from rkjo_kernel.tools.policy import (
    ToolExecutionDecision,
    ToolExecutionPolicy,
)
from rkjo_kernel.tools.registry import ToolRegistry


@dataclass(frozen=True)
class ToolExecutionResult:
    success: bool
    output: Any = None
    error: str | None = None


class ToolInvoker:
    """Execute handlers registered in ToolRegistry."""

    def __init__(
        self,
        registry: ToolRegistry,
        policy: ToolExecutionPolicy | None = None,
        approval_service: ToolApprovalService | None = None,
    ) -> None:
        self.registry = registry
        self.policy = policy or ToolExecutionPolicy()
        self.approval_service = approval_service

    def invoke(
        self,
        tool_name: str,
        payload: dict[str, Any],
        context: Any = None,
    ) -> ToolExecutionResult:
        """Invoke a registered tool without capability authorization.

        This method is kept for backward compatibility and low-level runtime
        use. Agent/capability execution should use ``invoke_authorized``.
        """
        return self._invoke_registered(
            tool_name=tool_name,
            payload=payload,
            context=context,
        )

    def invoke_authorized(
        self,
        *,
        capability: AgentCapability,
        tool_name: str,
        payload: dict[str, Any],
        context: ToolExecutionContext,
    ) -> ToolExecutionResult:
        """Invoke a tool only when allowed by the capability policy."""
        normalized_tool_name = tool_name.strip().lower()
        registered_tool = self.registry.get_registered_tool(
            normalized_tool_name
        )
        descriptor = (
            registered_tool.descriptor
            if registered_tool is not None
            else None
        )
        decision = self.policy.evaluate(
            capability=capability,
            tool_name=normalized_tool_name,
            context=context,
            descriptor=descriptor,
        )

        if decision == ToolExecutionDecision.REQUIRE_APPROVAL:
            approval_id = context.metadata.get("approval_id")
            approved = (
                isinstance(approval_id, str)
                and self.approval_service is not None
                and self.approval_service.authorize(
                    approval_id=approval_id,
                    tenant_id=context.tenant_id,
                    tool_name=normalized_tool_name,
                    mission_id=context.mission_id,
                    trace_id=context.trace_id,
                )
            )
            if not approved:
                return ToolExecutionResult(
                    success=False,
                    error=(
                        f"Tool '{normalized_tool_name}' requires durable "
                        "approval before execution."
                    ),
                )
            decision = ToolExecutionDecision.ALLOW

        if decision != ToolExecutionDecision.ALLOW:
            return ToolExecutionResult(
                success=False,
                error=(
                    f"Tool '{normalized_tool_name}' "
                    f"is not authorized for capability "
                    f"'{capability.name}'."
                ),
            )

        return self._invoke_registered(
            tool_name=normalized_tool_name,
            payload=payload,
            context=context,
        )

    def _invoke_registered(
        self,
        *,
        tool_name: str,
        payload: dict[str, Any],
        context: Any,
    ) -> ToolExecutionResult:
        registered_tool = self.registry.get_registered_tool(
            tool_name
        )

        if registered_tool is None:
            return ToolExecutionResult(
                success=False,
                error=(
                    f"Tool '{tool_name}' "
                    "is not registered."
                ),
            )

        if registered_tool.handler is None:
            return ToolExecutionResult(
                success=False,
                error=(
                    f"Tool '{tool_name}' "
                    "has no registered handler."
                ),
            )

        try:
            output = registered_tool.handler(
                payload,
                context,
            )

            return ToolExecutionResult(
                success=True,
                output=output,
            )

        except Exception as exc:
            return ToolExecutionResult(
                success=False,
                error=str(exc),
            )
