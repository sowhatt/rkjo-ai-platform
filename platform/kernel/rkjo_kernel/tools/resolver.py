from rkjo_kernel.registry.discovery import DiscoveryResult
from rkjo_kernel.tools.descriptor import ToolDescriptor
from rkjo_kernel.tools.registry import ToolRegistry


class CapabilityToolResolver:
    """
    Resolve the tools declared by the selected capability.

    The resolver does not select agents and does not execute tools.
    AgentDiscovery remains responsible for agent selection.
    ToolInvoker remains responsible for execution.
    """

    def __init__(
        self,
        registry: ToolRegistry,
    ) -> None:
        self.registry = registry

    def resolve(
        self,
        discovery_result: DiscoveryResult,
    ) -> list[ToolDescriptor]:
        resolved_tools: list[ToolDescriptor] = []

        for tool_name in discovery_result.capability.tools:
            descriptor = self.registry.find_by_name(
                tool_name
            )

            if descriptor is None:
                raise KeyError(
                    f"Tool '{tool_name}' "
                    "is not registered."
                )

            resolved_tools.append(
                descriptor
            )

        return resolved_tools
