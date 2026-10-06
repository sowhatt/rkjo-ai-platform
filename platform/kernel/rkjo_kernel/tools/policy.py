from enum import Enum

from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.tools.context import ToolExecutionContext
from rkjo_kernel.tools.descriptor import ToolDescriptor


class ToolExecutionDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class ToolExecutionPolicy:
    """Fail-closed authorization for capability-bound tool execution."""

    def evaluate(
        self,
        *,
        capability: AgentCapability,
        tool_name: str,
        context: ToolExecutionContext,
        descriptor: ToolDescriptor | None = None,
    ) -> ToolExecutionDecision:
        normalized_tool_name = tool_name.strip().lower()
        if not normalized_tool_name:
            raise ValueError("Tool name cannot be empty.")

        if context.capability_name != capability.name:
            return ToolExecutionDecision.DENY
        if normalized_tool_name not in capability.tools:
            return ToolExecutionDecision.DENY

        if descriptor is not None and bool(
            descriptor.metadata.get("requires_approval", False)
        ):
            approval = context.metadata.get("tool_approval")
            if not isinstance(approval, dict):
                return ToolExecutionDecision.REQUIRE_APPROVAL
            if approval.get("tool_name") != normalized_tool_name:
                return ToolExecutionDecision.REQUIRE_APPROVAL
            if approval.get("approved") is not True:
                return ToolExecutionDecision.REQUIRE_APPROVAL

        return ToolExecutionDecision.ALLOW
