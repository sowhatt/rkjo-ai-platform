from dataclasses import dataclass
from typing import Any

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
    ) -> None:
        self.registry = registry

    def invoke(
        self,
        tool_name: str,
        payload: dict[str, Any],
        context: Any = None,
    ) -> ToolExecutionResult:
        registered_tool = (
            self.registry.get_registered_tool(
                tool_name
            )
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
