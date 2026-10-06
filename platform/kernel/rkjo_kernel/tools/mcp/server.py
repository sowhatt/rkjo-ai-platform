"""RKJO MCP server facade.

Exposes explicitly allowed RKJO capabilities through MCP without bypassing
ToolRegistry, ToolExecutionPolicy or durable HITL approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.tools.context import ToolExecutionContext
from rkjo_kernel.tools.invoker import ToolInvoker
from rkjo_kernel.tools.registry import ToolRegistry


@dataclass(frozen=True, slots=True)
class MCPServerTool:
    name: str
    description: str
    input_schema: dict[str, Any]


class RKJOMCPServer:
    """Protocol-level MCP facade over RKJO's authorized Tool Runtime."""

    def __init__(
        self,
        *,
        registry: ToolRegistry,
        invoker: ToolInvoker,
        capabilities: list[AgentCapability],
        exposed_capabilities: set[str],
    ) -> None:
        self.registry = registry
        self.invoker = invoker
        self._capabilities = {item.name: item for item in capabilities}
        self._exposed = {
            name.strip().lower()
            for name in exposed_capabilities
            if name.strip()
        }

        unknown = self._exposed.difference(self._capabilities)
        if unknown:
            raise ValueError(
                "Cannot expose unknown MCP capabilities: "
                + ", ".join(sorted(unknown))
            )

    def list_tools(self) -> list[MCPServerTool]:
        tools: list[MCPServerTool] = []
        for capability_name in sorted(self._exposed):
            capability = self._capabilities[capability_name]
            for tool_name in capability.tools:
                descriptor = self.registry.find_by_name(tool_name)
                if descriptor is None:
                    continue
                tools.append(MCPServerTool(
                    name=self._external_name(capability.name, descriptor.name),
                    description=descriptor.description,
                    input_schema=dict(descriptor.input_schema),
                ))
        return tools

    def call_tool(
        self,
        *,
        name: str,
        arguments: dict[str, Any],
        context: ToolExecutionContext | None,
    ) -> Any:
        if context is None:
            raise PermissionError(
                "RKJO MCP execution requires a ToolExecutionContext."
            )

        capability, tool_name = self._resolve(name)

        if context.capability_name != capability.name:
            raise PermissionError(
                "MCP execution context does not match exposed capability."
            )

        result = self.invoker.invoke_authorized(
            capability=capability,
            tool_name=tool_name,
            payload=dict(arguments),
            context=context,
        )
        if not result.success:
            raise PermissionError(result.error or "RKJO MCP tool execution denied.")
        return result.output

    def handle(
        self,
        *,
        method: str,
        params: dict[str, Any] | None = None,
        context: ToolExecutionContext | None = None,
    ) -> dict[str, Any]:
        params = params or {}
        if method == "tools/list":
            return {
                "tools": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.input_schema,
                    }
                    for tool in self.list_tools()
                ]
            }
        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", {})
            if not isinstance(name, str) or not name.strip():
                raise ValueError("MCP tools/call requires a tool name.")
            if not isinstance(arguments, dict):
                raise ValueError("MCP tools/call arguments must be an object.")
            return {
                "content": self.call_tool(
                    name=name,
                    arguments=arguments,
                    context=context,
                )
            }
        raise KeyError(f"Unsupported RKJO MCP method '{method}'.")

    def _resolve(self, external_name: str) -> tuple[AgentCapability, str]:
        normalized = external_name.strip().lower()
        for capability_name in self._exposed:
            capability = self._capabilities[capability_name]
            for tool_name in capability.tools:
                if normalized == self._external_name(capability.name, tool_name):
                    return capability, tool_name
        raise PermissionError(
            f"MCP tool '{external_name}' is not exposed by RKJO."
        )

    @staticmethod
    def _external_name(capability_name: str, tool_name: str) -> str:
        safe_tool = tool_name.strip().lower().replace(".", "_")
        return f"rkjo.{capability_name}.{safe_tool}"
