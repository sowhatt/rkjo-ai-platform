from dataclasses import dataclass
from typing import Any

from rkjo_kernel.registry.capability import AgentCapability
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
    ) -> None:
        self.registry = registry
        self.policy = policy or ToolExecutionPolicy()

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
        decision = self.policy.evaluate(
            capability=capability,
            tool_name=tool_name,
            context=context,
        )

        if decision != ToolExecutionDecision.ALLOW:
            return ToolExecutionResult(
                success=False,
                error=(
                    f"Tool '{tool_name.strip().lower()}' "
                    f"is not authorized for capability "
                    f"'{capability.name}'."
                ),
            )

        return self._invoke_registered(
            tool_name=tool_name.strip().lower(),
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
