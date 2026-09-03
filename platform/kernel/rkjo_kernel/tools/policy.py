from enum import Enum

from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.tools.context import ToolExecutionContext


class ToolExecutionDecision(str, Enum):
    """Decision returned by the tool execution policy."""

    ALLOW = "allow"
    DENY = "deny"


class ToolExecutionPolicy:
    """Authorize tool execution against a capability and execution context."""

    def evaluate(
        self,
        *,
        capability: AgentCapability,
        tool_name: str,
        context: ToolExecutionContext,
    ) -> ToolExecutionDecision:
        normalized_tool_name = tool_name.strip().lower()

        if not normalized_tool_name:
            raise ValueError("Tool name cannot be empty.")

        if context.capability_name != capability.name:
            return ToolExecutionDecision.DENY

        if normalized_tool_name not in capability.tools:
            return ToolExecutionDecision.DENY

        return ToolExecutionDecision.ALLOW
